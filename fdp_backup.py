# v1.3 31-03-2025

import requests
import rdflib
from rdflib import Graph, Namespace
from datetime import datetime
from urllib.parse import urlparse
import os
import re
import csv
from rdflib.namespace import NamespaceManager
from concurrent.futures import ThreadPoolExecutor
from rdflib.namespace import FOAF
import shutil

LDP = Namespace('http://www.w3.org/ns/ldp#')
RDF = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
DCT = Namespace('http://purl.org/dc/terms/')
DCAT = Namespace('http://www.w3.org/ns/dcat#')
ADMS = Namespace('http://www.w3.org/ns/adms#')
HEALTHDCATAP = Namespace('http://healthdataportal.eu/ns/health#')

# Format current date and time as YYYY-MM-DD_HH-MM-SS
now = datetime.now()
today_date = now.strftime('%Y-%m-%d')
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/app/backup")
STATUS_LOG = os.path.join(BACKUP_DIR, f"backup_status_{today_date}.log")
FDP_URLS_FILE = os.environ.get("FDP_URLS_FILE", "/app/config/fdp_urls.txt")


try:
    with open(FDP_URLS_FILE, "r") as f:
        fdpURLs = [line.strip() for line in f.readlines() if line.strip()]
except Exception as e:
    print(f"❌ Could not read FDP_URLS_FILE: {FDP_URLS_FILE}\n{e}")
    fdpURLs = []

def write_status_log(message):
    timestamped = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {message}"
    with open(STATUS_LOG, "a") as log:
        log.write(timestamped + "\n")


# Sanitize file/folder names
def sanitize_filename(name):
    name = re.sub(r'@.*', '', name)
    name = re.sub(r'[^A-Za-z0-9-_ ]', '', name)
    name = name.replace(' ', '_')
    return name.strip().lower()

def backup_fdp(fdpURL):
    parsed_url = urlparse(fdpURL)
    base_fdp_uri = parsed_url.hostname

    # Subfolder per FDP host
    fdp_subfolder = os.path.join(BACKUP_DIR, base_fdp_uri)
    os.makedirs(fdp_subfolder, exist_ok=True)

    folder_name = f'FDP-Backup-{base_fdp_uri}-{timestamp}'
    folder_path = os.path.join(fdp_subfolder, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    print(f'\n🔄 Starting backup for {fdpURL}')

    headers = {'Accept': 'text/turtle'}
    try:
        res = requests.get(fdpURL, headers=headers)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching root FDP from {fdpURL}: {e}")
        write_status_log(f" ERROR   | {base_fdp_uri} | Failed to fetch root FDP: {e}")
        return

    fdpStore = Graph()
    fdpStore.parse(data=res.text, format="turtle")

    allCatalogues = []
    for catalogue in fdpStore.subjects(RDF.type, LDP.DirectContainer):
        allCatalogues += list(fdpStore.objects(catalogue, LDP.contains))

    fdpStore.serialize(os.path.join(folder_path, 'FDP.ttl'), format='turtle')
    print(f'📦 Found {len(allCatalogues)} catalogues.')

    log_rows = []

    for index, catalogue_uri in enumerate(allCatalogues):
        try:
            resCatalogue = requests.get(catalogue_uri, headers=headers)
            resCatalogue.raise_for_status()
            catalogueStore = Graph()
            catalogueStore.parse(data=resCatalogue.text, format="turtle")
        except Exception as e:
            print(f"⚠️ Skipping catalogue {catalogue_uri}: {e}")
            continue

        catalogueTitles = list(catalogueStore.objects(None, DCT.title))
        allDatasets = list(catalogueStore.objects(None, DCAT.dataset))
        title = catalogueTitles[0] if catalogueTitles else f"catalogue_{index}"
        print(f"📁 Catalogue: {title} ({len(allDatasets)} datasets)")

        catalogue_title = sanitize_filename(str(title))
        catalogue_folder = os.path.join(folder_path, f'catalogue_{catalogue_title}')
        os.makedirs(catalogue_folder, exist_ok=True)

        catalogueStore.serialize(os.path.join(catalogue_folder, f'catalogue_{catalogue_title}.ttl'), format='turtle')

        for dataset in allDatasets:
            try:
                resDataset = requests.get(dataset, headers=headers)
                resDataset.raise_for_status()
                datasetStore = Graph()
                datasetStore.parse(data=resDataset.text, format='turtle')
            except Exception as e:
                print(f"⚠️ Skipping dataset {dataset}: {e}")
                continue

            datasetTitles = list(datasetStore.objects(None, DCT.title))
            dataset_title = sanitize_filename(str(datasetTitles[0])) if datasetTitles else f'dataset_{index}'

            allDistributions = list(datasetStore.objects(None, DCAT.distribution))
            allSamples = list(datasetStore.objects(None, ADMS.sample))
            allAnalytics = list(datasetStore.objects(None, HEALTHDCATAP.analytics))

            # Save subclass graphs
            for label, items, rdf_type in [
                ("distribution", allDistributions, DCAT.Distribution),
                ("sample", allSamples, ADMS.Sample),
                ("analytics", allAnalytics, HEALTHDCATAP.Analytics)
            ]:
                for item in items:
                    try:
                        subRes = requests.get(item, headers=headers)
                        subRes.raise_for_status()
                        tempStore = Graph()
                        tempStore.parse(data=subRes.text, format="turtle")
                        datasetStore += tempStore
                        titles = list(tempStore.objects(None, DCT.title))
                        if titles:
                            print(f"   ➕ {label.capitalize()}: {titles[0]}")
                    except Exception as e:
                        print(f"   ⚠️ Failed {label} {item}: {e}")

            dataset_path = os.path.join(catalogue_folder, f'dataset_{dataset_title}.ttl')
            datasetStore.serialize(dataset_path, format='turtle')

            log_rows.append([
                str(title),
                str(datasetTitles[0]) if datasetTitles else '',
                len(allDistributions),
                len(allSamples),
                len(allAnalytics)
            ])

    # Save CSV log
    csv_path = os.path.join(folder_path, 'catalogue_dataset_log.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Catalogue Title', 'Dataset Title', '#Distributions', '#Samples', '#Analytics'])
        writer.writerows(log_rows)

    print(f"✅ Backup completed for {fdpURL}, saved in: {folder_path}")

    # Zip the backup folder
    zip_filename = os.path.join(fdp_subfolder, f"{folder_name}.zip")
    shutil.make_archive(base_name=os.path.join(fdp_subfolder, folder_name), format='zip', root_dir=folder_path)
    shutil.rmtree(folder_path)

    print(f"🗜️ Zipped backup: {zip_filename}")
    write_status_log(f" SUCCESS | {base_fdp_uri} | {os.path.basename(zip_filename)}")

# Run backups in parallel
with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(backup_fdp, fdpURLs)
