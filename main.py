import logging
import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor
import sys
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import (
    Qt, QUrl, QTimer, pyqtSignal, pyqtSlot, QThread, 
    QThreadPool, QRect, QMimeData
)
from PyQt5.QtGui import (
    QIcon, QKeySequence, QFont, QCursor, QPainter, 
    QColor, QTextCharFormat, QTextDocument, QTextOption, QDragEnterEvent, QDropEvent
)
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QMessageBox, QSpinBox, 
    QVBoxLayout, QHBoxLayout, QPushButton, QWidget, 
    QMainWindow, QCheckBox, QLineEdit, QScrollArea, 
    QPlainTextEdit, QLCDNumber, QListWidget, QDockWidget, 
    QComboBox, QFrame, QInputDialog, QLabel, QDialogButtonBox, 
    QDialog, QGridLayout, QMenu, QAction, QTabBar, 
    QRadioButton, QSystemTrayIcon, QShortcut
)
from PyQt5.QtXml import QDomDocument
from PyQt5.QtWidgets import QScrollBar, QDialog
from PyQt5.QtGui import QDesktopServices, QTextCursor
from CashOut_Cookie_Checker import Ui_Ui_CashOut_Cookie_Checker
from cookie_handler import CookieHandler
from config_processor import ConfigProcessor, load_config
from requests.exceptions import RequestException, Timeout
from data import config
import asyncio
import logging
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_CHECKBOXES = 18
CONFIG_FILE_PATTERN = ["configs/*.proj", "configs/*.cash"]
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
configs_dir = os.path.join(parent_dir, 'configs')


class CookieChecker:
    def __init__(self):
        self.MAX_CHECKBOXES = 20
        self.CONFIG_FILE_PATTERN = "config_{}.cash"  # Adjust as needed
        self.configs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs')

    def get_domain(self):
        config_files = self.get_selected_config_files()
        for config_file in config_files:
            config = self.load_config(config_file)
            if 'domain' in config:
                return config['domain']
        return "example.com"  # Default domain if not found

    def start_check_and_run(self):
        num_threads = self.threaddial.value()
        if num_threads <= 0:
            QMessageBox.critical(self, "Error", "The number of threads must be greater than 0.")
            return

        config_files = self.get_selected_config_files()
        if not config_files:
            QMessageBox.warning(self, "Warning", "No valid config files selected. Please select .cash or .proj files.")
            return

        self.display_selected_files(config_files)
        config_settings = [self.load_config(file) for file in config_files]
        self.display_config_settings(config_settings)

        all_cookie_files = self.get_all_cookie_files(config_settings)
        total_cookies = len(all_cookie_files)

        if total_cookies == 0:
            QMessageBox.warning(self, "Warning", "No cookie files found for the specified domains.")
            return

        if not self.confirm_process(len(config_files), total_cookies):
            return

        self.run_config_processor(num_threads, config_files, all_cookie_files)

    def load_cookies_function(self):
        options = QFileDialog.Options()
        directory_path = QFileDialog.getExistingDirectory(self, "Select Directory", "", options=options)
        if directory_path:
            self.directory_path_textedit.setText(directory_path)
            self.cookie_handler.load_cookies_from_directory(directory_path)
            domain = self.get_domain()
            cookie_files = self.cookie_handler.get_cookie_files(directory_path, domain)
            total_cookies = len(cookie_files)
            self.total_cookies_label.setText(f"Total Cookies: {total_cookies}")

    def display_config_settings(self, config_settings):
        self.configs_loaded_value_response_textedit.clear()
        all_settings_text = ""
        for i, config in enumerate(config_settings, 1):
            settings_text = (f"Config {i}:\n"
                             f"  Project Name: {config.get('project_name', 'N/A')}\n"
                             f"  Domain: {config.get('domain', 'N/A')}\n"
                             f"  Response Valid: {config.get('response_valid', 'N/A')}\n"
                             f"  URL: {config.get('url', 'N/A')}\n"
                             f"  Method: {config.get('method', 'N/A')}\n"
                             f"  Creator ID: {config.get('creator_id', 'N/A')}\n"
                             f"  From: /configs/{os.path.basename(config.get('file_path', 'Unknown'))}\n\n")
            all_settings_text += settings_text
        self.configs_loaded_value_response_textedit.setPlainText(all_settings_text)

    def load_config(self, file_path):
        config = configparser.ConfigParser()
        config.read(file_path)
        return {
            'project_name': config.get('CA$H Settings', 'ProjectName', fallback='Unknown Project'),
            'domain': config.get('Request Settings', 'Domain', fallback='Unknown'),
            'response_valid': config.get('Request Settings', 'ResponseValide', fallback=''),
            'url': config.get('Request Settings', 'URL', fallback=''),
            'method': config.get('Request Settings', 'Method', fallback='GET'),
            'creator_id': config.get('Security', 'CreatorID', fallback='Unknown'),
            'file_path': file_path
        }

    def get_selected_config_files(self):
        config_files = []
        for i in range(1, self.MAX_CHECKBOXES + 1):
            checkbox = getattr(self, f"checkBox_{i}", None)
            if checkbox and checkbox.isChecked():
                file_name = checkbox.text()
                file_path = os.path.join(self.configs_dir, file_name)
                if os.path.isfile(file_path) and file_path.lower().endswith(('.cash', '.proj')):
                    config_files.append(file_path)
                else:
                    self.log_message(f"Warning: Selected file {file_path} is not a valid .cash or .proj file.")
        return config_files

    def get_all_cookie_files(self, config_settings):
        all_cookie_files = []
        for config in config_settings:
            domain = config.get('domain')
            if domain:
                cookie_files = self.cookie_handler.get_cookie_files(self.configs_dir, domain)
                all_cookie_files.extend(cookie_files)
        return all_cookie_files

    def confirm_process(self, num_configs, total_cookies):
        reply = QMessageBox.question(self, 'Confirm Check Process', 
                                     f"Start check process with {num_configs} configs and {total_cookies} cookie files?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    def run_config_processor(self, num_threads, config_files, all_cookie_files):
        self.config_processor = ConfigProcessor(num_threads)
        self.config_processor.progress_updated.connect(self.update_progress)
        self.config_processor.error_occurred.connect(self.log_message)
        self.config_processor.finished.connect(self.on_check_process_finished)
        self.config_processor.run_check_process(self.configs_dir, config_files, all_cookie_files)

    def update_progress(self, value, message):
        self.progressBar.setValue(value)
        self.log_message(message)

    def on_check_process_finished(self, results):
        self.log_message("Check process completed. Results:")
        for domain, cookie_count in results.items():
            self.log_message(f"Domain: {domain}, Cookies: {cookie_count}")

    def log_message(self, message):
        self.cookies_details_request_textedit.append(message)

    def display_selected_files(self, files):
        self.http_response_textEdit.append("Selected config files:")
        for file in files:
            self.http_response_textEdit.append(file)
        self.http_response_textEdit.append("")

class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super(SearchDialog, self).__init__(parent)
        self.setWindowTitle("Search")
        self.setGeometry(100, 100, 300, 100)
        
        self.search_label = QLabel("Find:")
        self.search_input = QLineEdit(self)
        
        self.search_button = QPushButton("Search", self)
        self.search_button.clicked.connect(self.accept)

        layout = QHBoxLayout()
        layout.addWidget(self.search_label)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        
        self.setLayout(layout)
    
    def get_search_term(self):
        return self.search_input.text()
    def set_result_count(self, count):
        self.result_label.setText(f"Occurrences: {count}")

class DragDropCheckBox(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        file_loaded = pyqtSignal(str)  # Signal to emit when a file is loaded

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.lower().endswith(('.proj', '.cash')):
                event.acceptProposedAction()


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        drag.setMimeData(mime_data)

        drag.exec_(Qt.CopyAction | Qt.MoveAction)

    def set_file(self, file_path):
        if file_path.lower().endswith('.cash'):
            self.setChecked(True)
            self.setText(os.path.basename(file_path))
            self.setToolTip(file_path)
            self.file_loaded.emit(file_path)

    def dropEvent(self, event: QDropEvent):
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.set_file(file_path)
        event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        if self.isChecked():
            file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Cash Files (*.cash)")
            if file_path:
                self.set_file(file_path)
        else:
            super().mouseDoubleClickEvent(event)

    def process_cash_file(self, file_path):
        config = configparser.ConfigParser()
        config.read(file_path)

        project_name = config.get('CA$H Settings', 'ProjectName', fallback='N/A')
        capture1 = config.get('Parser Settings', 'Capture1Value', fallback='N/A')
        capture2 = config.get('Parser Settings', 'Capture2Value', fallback='N/A')
        capture3 = config.get('Parser Settings', 'Capture3Value', fallback='N/A')
        creator_id = config.get('Security', 'CreatorID', fallback='N/A')

        display_text = f"{project_name} - {capture1} | {capture2} | {capture3} - {creator_id}"
        
        current_text = self.configs_loaded_value_response_textedit.toPlainText()
        if current_text:
            current_text += "\n"
        self.configs_loaded_value_response_textedit.setPlainText(current_text + display_text)

class ConfigConfirmationDialog(QDialog):
    def __init__(self, configs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Configurations")
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText("\n".join(configs))
        layout.addWidget(text_edit)
        
        confirm_button = QPushButton("Confirm and Start")
        confirm_button.clicked.connect(self.accept)
        layout.addWidget(confirm_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)
        
        self.setLayout(layout)

class MainWindow(QMainWindow, Ui_Ui_CashOut_Cookie_Checker):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # This method is defined in the generated file
        self.shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut.activated.connect(self.open_search_dialog)
        # Create a vertical layout for the main window if not already defined in the UI
        self.main_layout = QVBoxLayout(self.centralWidget())  # Assuming you have a central widget

        # Connect buttons and other UI elements
        self.load_cookies_button.clicked.connect(self.load_cookies_function)
        self.start_checker_button.clicked.connect(self.start_check_and_run)
        self.shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut.activated.connect(self.open_search_dialog)

        # Set up the system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('cookie_creator.ico'))  # Set the tray icon
        self.tray_icon.show()

        # Create a vertical layout for checkboxes
        self.checkbox_layout = QVBoxLayout()
        
        self.checkBox_1.stateChanged.connect(lambda state, checkbox=self.checkBox_1: self.open_file_dialog(state, checkbox))
        self.checkBox_2.stateChanged.connect(lambda state, checkbox=self.checkBox_2: self.open_file_dialog(state, checkbox))
        self.checkBox_3.stateChanged.connect(lambda state, checkbox=self.checkBox_3: self.open_file_dialog(state, checkbox))
        self.checkBox_4.stateChanged.connect(lambda state, checkbox=self.checkBox_4: self.open_file_dialog(state, checkbox))
        self.checkBox_5.stateChanged.connect(lambda state, checkbox=self.checkBox_5: self.open_file_dialog(state, checkbox))
        self.checkBox_6.stateChanged.connect(lambda state, checkbox=self.checkBox_6: self.open_file_dialog(state, checkbox))
        self.checkBox_7.stateChanged.connect(lambda state, checkbox=self.checkBox_7: self.open_file_dialog(state, checkbox))
        self.checkBox_8.stateChanged.connect(lambda state, checkbox=self.checkBox_8: self.open_file_dialog(state, checkbox))
        self.checkBox_9.stateChanged.connect(lambda state, checkbox=self.checkBox_9: self.open_file_dialog(state, checkbox))
        self.checkBox_10.stateChanged.connect(lambda state, checkbox=self.checkBox_10: self.open_file_dialog(state, checkbox))
        self.checkBox_11.stateChanged.connect(lambda state, checkbox=self.checkBox_11: self.open_file_dialog(state, checkbox))
        self.checkBox_12.stateChanged.connect(lambda state, checkbox=self.checkBox_12: self.open_file_dialog(state, checkbox))
        self.checkBox_13.stateChanged.connect(lambda state, checkbox=self.checkBox_13: self.open_file_dialog(state, checkbox))
        self.checkBox_14.stateChanged.connect(lambda state, checkbox=self.checkBox_14: self.open_file_dialog(state, checkbox))
        self.checkBox_15.stateChanged.connect(lambda state, checkbox=self.checkBox_15: self.open_file_dialog(state, checkbox))
        self.checkBox_16.stateChanged.connect(lambda state, checkbox=self.checkBox_16: self.open_file_dialog(state, checkbox))
        self.checkBox_17.stateChanged.connect(lambda state, checkbox=self.checkBox_17: self.open_file_dialog(state, checkbox))
        self.checkBox_18.stateChanged.connect(lambda state, checkbox=self.checkBox_18: self.open_file_dialog(state, checkbox))
        self.checkBox_19.stateChanged.connect(lambda state, checkbox=self.checkBox_19: self.open_file_dialog(state, checkbox))
        self.checkBox_20.stateChanged.connect(lambda state, checkbox=self.checkBox_20: self.open_file_dialog(state, checkbox))
        self.checkBox_21.stateChanged.connect(lambda state, checkbox=self.checkBox_21: self.open_file_dialog(state, checkbox))
        self.checkBox_22.stateChanged.connect(lambda state, checkbox=self.checkBox_22: self.open_file_dialog(state, checkbox))
        self.checkBox_23.stateChanged.connect(lambda state, checkbox=self.checkBox_23: self.open_file_dialog(state, checkbox))
        self.checkBox_24.stateChanged.connect(lambda state, checkbox=self.checkBox_24: self.open_file_dialog(state, checkbox))
        self.checkboxes = []

        self.checkbox = DragDropCheckBox("Drag .proj or .cash file here")
        self.threaddial.valueChanged.connect(self.update_thread_label)
        # For configs_loaded_value_response_textedit
        self.configs_loaded_value_response_textedit.setReadOnly(True)
        self.configs_loaded_value_response_textedit.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        
        # For configs_loaded_value_response_textedit
        self.configs_loaded_value_response_textedit.setReadOnly(True)
        self.configs_loaded_value_response_textedit.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        
        # For http_response_textEdit
        self.http_response_textEdit.setReadOnly(True)
        self.http_response_textEdit.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.cookie_handler = CookieHandler()
        self.cookie_handler.progress_updated.connect(self.update_progress_bar)
        self.cookie_handler.error_occurred.connect(self.show_error)
        self.cookie_handler.total_cookies_updated.connect(self.update_total_cookies_loaded)

    def show_error(self, error_message):
        self.cookies_details_request_textedit.append(f"Error: {error_message}")

    def update_total_cookies_loaded(self, value):
        self.total_cookies_loaded_lcdNumber.display(value)


    def update_ui(self, message, is_progress=False):
        if is_progress:
            self.update_progress_bar(message)
        else:
            self.cookies_details_request_textedit.append(message)

    def open_search_dialog(self):
        dialog = SearchDialog(self)
        if dialog.exec_():
            search_term = dialog.get_search_term()
            self.perform_search(search_term)


    def process_cash_file(self, file_path):
        config = configparser.ConfigParser()
        config.read(file_path)

        project_name = config.get('CA$H Settings', 'ProjectName', fallback='N/A')
        capture1 = config.get('Parser Settings', 'Capture1Value', fallback='N/A')
        capture2 = config.get('Parser Settings', 'Capture2Value', fallback='N/A')
        capture3 = config.get('Parser Settings', 'Capture3Value', fallback='N/A')
        creator_id = config.get('Security', 'CreatorID', fallback='N/A')

        display_text = f"{project_name} - {capture1} | {capture2} | {capture3} - {creator_id}"
        
        current_text = self.configs_loaded_value_response_textedit.toPlainText()
        if current_text:
            current_text += "\n"
        self.configs_loaded_value_response_textedit.setPlainText(current_text + display_text)

    
    def open_file_dialog(self, state, checkbox):
        # Check if the checkbox is checked
        if state == Qt.Checked:
            # Open file dialog with specific filters
            options = QFileDialog.Options()
            file_types = "All Files (*);;CA$H Files (*.cash);;Proj Files (*.proj)"
            file_name, _ = QFileDialog.getOpenFileName(self, "Select a File", "", file_types, options=options)
            if file_name:
                logging.info(f"Selected file: {file_name}")
                # Set the checkbox text to just the file name (not the full path)
                file_basename = os.path.basename(file_name)
                checkbox.setText(file_basename)

                # Display the selected file name in the QTextEdit
                self.cookies_details_request_textedit.append(f"Loaded file: {file_basename}")
        else:
            # Optionally reset the checkbox text if unchecked
            checkbox.setText(f"CheckBox_{checkbox.objectName()[-1]}")  # Reset to original name


    def load_cookies_function(self):
        options = QFileDialog.Options()
        directory_path = QFileDialog.getExistingDirectory(self, "Select Directory", "", options=options)
        if directory_path:
            self.directory_path_textedit.setText(directory_path)
            self.cookie_handler.load_cookies_from_directory(directory_path)

    def update_progress(self, value, message):
        self.progressBar.setValue(value)
        self.cookies_details_request_textedit.append(message)

    def update_thread_label(self, value):
        self.threadNumber.display(value)


    def update_progress_bar(self, value):
        """
        Update the progress bar with the given value.
        
        :param value: A float between 0 and 100 representing the progress percentage.
        """
        try:
            # Ensure the value is between 0 and 100
            value = max(0, min(100, value))
            
            # Update the progress bar value
            self.progressBar.setValue(int(value))
            
            # Force the GUI to update immediately
            self.progressBar.repaint()
            
            # Optionally, update a status label if you have one
            status_text = f"Progress: {value:.1f}%"
            if hasattr(self, 'statusLabel'):
                self.statusLabel.setText(status_text)
            
            # If the progress is complete, you might want to do something special
            if value == 100:
                self.progressBar.setFormat("Complete!")
                # Optionally, reset the progress bar after a delay
                QtCore.QTimer.singleShot(2000, self.reset_progress_bar)
            else:
                self.progressBar.setFormat("%p%")  # Show percentage
            
            # Process any pending events to keep the UI responsive
            QtWidgets.QApplication.processEvents()
            
        except Exception as e:
            logging.error(f"Error updating progress bar: {e}")




    def reset_progress_bar(self):
        """Reset the progress bar to 0 and clear any completion message."""
        self.progressBar.setValue(0)
        self.progressBar.setFormat("%p%")






########################################################################################################################################################################################################################################################################################

    def get_domain(self):
        directory_path = self.directory_path_textedit.toPlainText().strip()
        
        # Get the selected config files
        config_files = []
        for i in range(MAX_CHECKBOXES):
            checkbox = getattr(self, f"checkBox_{i+1}", None)
            if checkbox and checkbox.isChecked():
                if isinstance(CONFIG_FILE_PATTERN, list):
                    pattern = CONFIG_FILE_PATTERN[i % len(CONFIG_FILE_PATTERN)]
                else:
                    pattern = CONFIG_FILE_PATTERN
                
                config_path = pattern.format(i + 1)
                file_path = os.path.join(directory_path, config_path)
                if os.path.isfile(file_path) and file_path.lower().endswith(('.cash', '.proj')):
                    config_files.append(file_path)
    
                    # Try to get the domain from the first valid config file
                    for config_file in config_files:
                        config = load_config(config_file)
                        if 'domain' in config:
                            return config['domain']
                    
                    # If no domain is found, return a default value or raise an exception
                    return "example.com"  # or raise ValueError("No domain found in config files")
                    
    
    def start_check_and_run(self):
        num_threads = self.threaddial.value()
        
        # Use the configs directory instead of the directory from the text edit
        directory_path = configs_dir
    
        if num_threads <= 0:
            QMessageBox.critical(self, "Error", "The number of threads must be greater than 0.")
            return
    
        # Collect config files
        config_files = []
        for i in range(1, 21):  # Assuming you have checkboxes from 1 to 20
            checkbox = getattr(self, f"checkBox_{i}", None)
            if checkbox and checkbox.isChecked():
                file_name = checkbox.text()  # Assuming the checkbox text contains the file name
                file_path = os.path.join(directory_path, file_name)
                if os.path.isfile(file_path) and file_path.lower().endswith(('.cash', '.proj')):
                    config_files.append(file_path)
                else:
                    self.http_response_textEdit.append(f"Warning: Selected file {file_path} is not a valid .cash or .proj file.")
    
        if not config_files:
            QMessageBox.warning(self, "Warning", "No valid config files selected. Please select .cash or .proj files.")
            return
    
        # Display selected config files
        self.http_response_textEdit.append("Selected config files:")
        for file in config_files:
            self.http_response_textEdit.append(file)
        self.http_response_textEdit.append("")
    
    
        # Load and display config settings
        config_settings = []
        for file_path in config_files:
            config = self.load_config(file_path)
            config_settings.append(config)
        self.display_config_settings(config_settings)
    
        # Get cookie files for each domain specified in the config files
        all_cookie_files = []
        for config in config_settings:
            domain = config.get('Request Settings', {}).get('Domain')
            if domain:
                cookie_files = self.cookie_handler.get_cookie_files(directory_path, domain)
                all_cookie_files.extend(cookie_files)
    
        total_cookies = len(all_cookie_files)
    
        if total_cookies == 0:
            QMessageBox.warning(self, "Warning", "No cookie files found for the specified domains.")
            return
    
        # Ask for confirmation
        reply = QMessageBox.question(self, 'Confirm Check Process', 
                                    f"Start check process with {len(config_files)} configs and {total_cookies} cookie files?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
    
        # Initialize and run the config processor
        self.config_processor = ConfigProcessor(num_threads)
        self.config_processor.progress_updated.connect(self.update_progress)
        self.config_processor.error_occurred.connect(self.log_message)
        self.config_processor.finished.connect(self.on_check_process_finished)
    
        # Pass the cookie files to the config processor
        self.config_processor.run_check_process(directory_path, config_files, all_cookie_files)

    def load_cookies_function(self):
        options = QFileDialog.Options()
        directory_path = QFileDialog.getExistingDirectory(self, "Select Directory", "", options=options)
        if directory_path:
            self.directory_path_textedit.setText(directory_path)
            self.cookie_handler.load_cookies_from_directory(directory_path)
            
            # Define the domain
            domain = "example.com"  # Replace with the actual domain you want to use
            
            # Update the total cookies label
            cookie_files = self.cookie_handler.get_cookie_files(directory_path, domain)
            total_cookies = len(cookie_files)  # Assuming get_cookie_files returns a list
            self.total_cookies_label.setText(f"Total Cookies: {total_cookies}")
    

    def display_config_settings(self, config_settings):
        self.configs_loaded_value_response_textedit.clear()
        all_settings_text = ""
        for i, config in enumerate(config_settings, 1):
            settings_text = f"Config {i}:\n"
            settings_text += f"  Project Name: {config.get('project_name', 'N/A')}\n"
            settings_text += f"  Domain: {config.get('domain', 'N/A')}\n"
            settings_text += f"  Response Valid: {config.get('response_valid', 'N/A')}\n"
            settings_text += f"  URL: {config.get('url', 'N/A')}\n"
            settings_text += f"  Method: {config.get('method', 'N/A')}\n"
            settings_text += f"  Creator ID: {config.get('creator_id', 'N/A')}\n"
            settings_text += f"  From: /configs/{os.path.basename(config.get('file_path', 'Unknown'))}\n\n"
            all_settings_text += settings_text
        self.configs_loaded_value_response_textedit.setPlainText(all_settings_text)
    
    def update_progress(self, value, message):
        self.progressBar.setValue(value)
        self.log_message(message)
    
    def on_check_process_finished(self, results):
        self.log_message("Check process completed. Results:")
        for domain, cookie_count in results.items():
            self.log_message(f"Domain: {domain}, Cookies: {cookie_count}")
        # Update UI or perform any other necessary actions
    
    def log_message(self, message):
        self.cookies_details_request_textedit.append(message)

    def load_selected_configs(self):
        configs = []
        config_files = []
        directory_path = os.path.join(self.directory_path_textedit.toPlainText().strip(), 'configs')
        for i in range(MAX_CHECKBOXES):
            checkbox = getattr(self, f"checkBox_{i+1}", None)
            if checkbox and checkbox.isChecked():
                config_path = CONFIG_FILE_PATTERN.format(i + 1)
                file_path = os.path.join(directory_path, config_path)
                if os.path.isfile(file_path) and file_path.lower().endswith(('.cash', '.proj')):
                    config = load_config(file_path)
                    configs.append(config)
                    config_files.append(file_path)
        return configs, config_files



    def load_config(file_path):
        config = configparser.ConfigParser()
        config.read(file_path)
        return {
            'project_name': config.get('CA$H Settings', 'ProjectName', fallback='Unknown Project'),
            'domain': config.get('Request Settings', 'Domain', fallback='Unknown'),
            'response_valid': config.get('Request Settings', 'ResponseValide', fallback=''),
            'url': config.get('Request Settings', 'URL', fallback=''),
            'method': config.get('Request Settings', 'Method', fallback='GET'),
            'creator_id': config.get('Security', 'CreatorID', fallback='Unknown'),
            'file_path': file_path  # Store the full file path
        }



    def display_config_settings(self, config_settings):
        self.configs_loaded_value_response_textedit.clear()
        for i, config in enumerate(config_settings, 1):
            settings_text = f"Config {i}:\n"
            settings_text += f"  Project Name: {config['project_name']}\n"
            settings_text += f"  Domain: {config['domain']}\n"
            settings_text += f"  Response Valid: {config['response_valid']}\n"
            settings_text += f"  URL: {config['url']}\n"
            settings_text += f"  Method: {config['method']}\n"
            settings_text += f"  Creator ID: {config['creator_id']}\n\n"
            self.configs_loaded_value_response_textedit.append(settings_text)








########################################################################################################################################################################################################













    def read_config_name(self, file_path):
        # Implement this method to read the project name from the config file
        # For example:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith("ProjectName="):
                    return line.split("=")[1].strip()
        return "Unknown Project"
    
    def process_config_file(self, file_path, directory_path):
        cookie_count = 0
        configs_loaded = 0
        try:
            cookie_count += self.process_netscape_cookie(file_path)
            configs_loaded += 1
            
            with open(file_path, 'r') as file:
                proj_data = file.read()
            
            project_settings = self.read_project_settings(file_path)
            domain = project_settings.get("Request Settings", "Domain")
            cookie_files = self.get_cookie_files(directory_path, domain)
    
            for cookie_file in cookie_files:
                response = self.process_cookies(cookie_file, project_settings)
                if response is not None:
                    self.log_message(response)
    
        except Exception as e:
            self.log_message(f"Error processing config file {file_path}: {str(e)}")
    
        return cookie_count, configs_loaded
    
    def log_message(self, message):
        self.http_response_textEdit.append(message)
    

    def display_results(self, cookie_count, configs_loaded):
        message = f"Processing completed.\n\n"
        message += f"Total cookies processed: {cookie_count}\n"
        message += f"Configurations loaded: {configs_loaded}"
        QMessageBox.information(self, "Results", message)




def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()