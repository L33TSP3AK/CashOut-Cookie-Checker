import os
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal

class ConfigProcessor(QObject):
    progress_updated = pyqtSignal(int, str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, num_threads):
        super().__init__()
        self.num_threads = num_threads

    def run_check_process(self, directory_path, config_files, total_cookies):
        self.progress_updated.emit(0, f"Starting check process with {total_cookies} cookies and {len(config_files)} configs...")
        
        results = {}
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_config = {executor.submit(self.process_config_file, config_file, directory_path): config_file 
                                for config_file in config_files}
            
            for i, future in enumerate(as_completed(future_to_config), 1):
                config_file = future_to_config[future]
                try:
                    domain, cookie_count = future.result()
                    results[domain] = cookie_count
                    progress = (i / len(config_files)) * 100
                    self.progress_updated.emit(int(progress), 
                        f"Processed config {i}/{len(config_files)}: {os.path.basename(config_file)} - Domain: {domain}, Cookies: {cookie_count}")
                except Exception as e:
                    self.error_occurred.emit(f"Error processing config file {config_file}: {str(e)}")

        self.progress_updated.emit(100, "Check process completed.")
        self.finished.emit(results)

    def process_config_file(self, config_file, directory_path):
        config = configparser.ConfigParser()
        config.read(config_file)
        
        domain = config.get('Request Settings', 'Domain', fallback='Unknown')
        cookie_count = self.count_cookies_for_domain(directory_path, domain)
        
        return domain, cookie_count

    def count_cookies_for_domain(self, directory_path, domain):
        cookie_count = 0
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith(('.txt', '.cash', '.proj')):
                    file_path = os.path.join(root, file)
                    cookie_count += self.count_domain_cookies_in_file(file_path, domain)
        return cookie_count

    def count_domain_cookies_in_file(self, file_path, domain):
        count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if domain in line:
                        count += 1
        except Exception as e:
            self.error_occurred.emit(f"Error reading file {file_path}: {str(e)}")
        return count

def load_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    return {
        'project_name': config.get('CA$H Settings', 'ProjectName', fallback='Unknown Project'),
        'domain': config.get('Request Settings', 'Domain', fallback='Unknown'),
        'response_valid': config.get('Request Settings', 'ResponseValide', fallback=''),
        'url': config.get('Request Settings', 'URL', fallback=''),
        'method': config.get('Request Settings', 'Method', fallback='GET'),
        'creator_id': config.get('Security', 'CreatorID', fallback='Unknown')
    }