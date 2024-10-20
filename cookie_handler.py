import os
import json
import logging
from PyQt5.QtCore import QObject, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed

class CookieHandler(QObject):
    progress_updated = pyqtSignal(int, str)
    error_occurred = pyqtSignal(str)
    total_cookies_updated = pyqtSignal(int)
    finished = pyqtSignal(int, dict)

    def __init__(self, max_workers=4):
        super().__init__()
        self.max_workers = max_workers
        self.total_cookies_loaded = 0
        self.cookie_data = {}

    def load_cookies_from_directory(self, directory_path):
        cookie_files = []
        for root, _, files in os.walk(directory_path):
            for f in files:
                if f.lower().endswith(('.txt', '.cash', '.proj')):
                    cookie_files.append(os.path.join(root, f))
        
        total_files = len(cookie_files)
        self.progress_updated.emit(0, f"Total cookie files found: {total_files}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.process_file, file_path): file_path 
                              for file_path in cookie_files}
            
            for i, future in enumerate(as_completed(future_to_file), 1):
                file_path = future_to_file[future]
                try:
                    cookies_processed, file_data = future.result()
                    self.total_cookies_loaded += cookies_processed
                    self.cookie_data.update(file_data)
                    progress = (i / total_files) * 100
                    self.progress_updated.emit(int(progress), 
                        f"Processed file {i}/{total_files}: {os.path.basename(file_path)} - {cookies_processed} cookies")
                    self.total_cookies_updated.emit(self.total_cookies_loaded)
                except Exception as e:
                    self.error_occurred.emit(f"Error processing file {file_path}: {str(e)}")

        self.progress_updated.emit(100, f"Finished loading all cookie files. Total cookies loaded: {self.total_cookies_loaded}")
        self.finished.emit(self.total_cookies_loaded, self.cookie_data)

    def process_file(self, file_path):
        cookies_processed = 0
        file_data = {}
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if self.is_valid_cookie_line(line):
                        cookie = self.process_cookie_line(line)
                        if cookie:
                            domain = cookie['domain']
                            if domain not in file_data:
                                file_data[domain] = []
                            file_data[domain].append(cookie)
                            cookies_processed += 1
        except Exception as e:
            self.error_occurred.emit(f"Error processing file {file_path}: {str(e)}")
        return cookies_processed, file_data

    def is_valid_cookie_line(self, line):
        return len(line.strip().split('\t')) >= 7

    def process_cookie_line(self, line):
        fields = line.strip().split('\t')
        if len(fields) >= 7:
            domain, _, path, secure, expires, name, value = fields[:7]
            return {
                'domain': domain,
                'path': path,
                'name': name,
                'value': value,
                'expires': expires,
                'secure': secure == 'TRUE'
            }
        return None

    def should_process_cookie(self, domain, name, project_settings):
        cookie_rules = project_settings.get('cookie_rules', {})
        if not cookie_rules:
            return True
        
        for rule_type in ['domains', 'names']:
            rules = cookie_rules.get(rule_type, {})
            for action in ['allow', 'block']:
                for pattern in rules.get(action, []):
                    if (rule_type == 'domains' and 
                        ((pattern.startswith('*.') and domain.endswith(pattern[1:])) or domain == pattern)) or \
                       (rule_type == 'names' and 
                        ((pattern.endswith('*') and name.startswith(pattern[:-1])) or name == pattern)):
                        return action == 'allow'
        
        return cookie_rules.get('default_action', 'allow') == 'allow'

    def get_cookie_files(self, directory_path, domain):
        cookie_files = []
        try:
            for filename in os.listdir(directory_path):
                if filename.endswith('.txt') and domain in filename:
                    cookie_files.append(os.path.join(directory_path, filename))
            return cookie_files
        except Exception as e:
            logging.error(f"Error retrieving cookie files: {e}")
            return []