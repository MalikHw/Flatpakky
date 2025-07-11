#!/usr/bin/env python3
"""
Flatpakky - A Flathub-like browser for Flatpaks
Created by MalikHw47
"""

import sys
import os
import json
import subprocess
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from urllib.request import urlopen, Request
from urllib.parse import quote
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QLineEdit, QTextEdit, QProgressBar, QStatusBar, QFrame,
    QScrollArea, QGroupBox, QCheckBox, QMessageBox, QFileDialog,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QGridLayout,
    QComboBox, QSpinBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QIcon, QFont, QAction, QDesktopServices
import tempfile
import urllib.request

class FlatpakAPI:
    """Handles communication with Flathub API and local Flatpak commands"""
    
    def __init__(self):
        self.base_url = "https://flathub.org/api/v1"
        self.apps_cache = {}
        self.icons_cache = {}
    
    def search_apps(self, query: str = "") -> List[Dict]:
        """Search for apps on Flathub"""
        try:
            if query:
                url = f"{self.base_url}/search/{quote(query)}"
            else:
                url = f"{self.base_url}/apps"
            
            req = Request(url, headers={'User-Agent': 'Flatpakky/1.0'})
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Error searching apps: {e}")
            return []
    
    def get_app_details(self, app_id: str) -> Dict:
        """Get detailed information about a specific app"""
        try:
            url = f"{self.base_url}/apps/{app_id}"
            req = Request(url, headers={'User-Agent': 'Flatpakky/1.0'})
            with urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Error getting app details: {e}")
            return {}
    
    def get_installed_apps(self) -> List[Dict]:
        """Get list of installed Flatpak applications"""
        try:
            result = subprocess.run(
                ['flatpak', 'list', '--app', '--columns=name,application,version,branch,origin'],
                capture_output=True, text=True, check=True
            )
            apps = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 5:
                        apps.append({
                            'name': parts[0],
                            'flatpakAppId': parts[1],
                            'currentReleaseVersion': parts[2],
                            'branch': parts[3],
                            'origin': parts[4]
                        })
            return apps
        except Exception as e:
            print(f"Error getting installed apps: {e}")
            return []
    
    def install_app(self, app_id: str) -> bool:
        """Install a Flatpak application"""
        try:
            subprocess.run(
                ['flatpak', 'install', 'flathub', app_id, '-y'],
                check=True
            )
            return True
        except Exception as e:
            print(f"Error installing app: {e}")
            return False
    
    def uninstall_app(self, app_id: str) -> bool:
        """Uninstall a Flatpak application"""
        try:
            subprocess.run(
                ['flatpak', 'uninstall', app_id, '-y'],
                check=True
            )
            return True
        except Exception as e:
            print(f"Error uninstalling app: {e}")
            return False
    
    def update_app(self, app_id: str) -> bool:
        """Update a specific Flatpak application"""
        try:
            subprocess.run(
                ['flatpak', 'update', app_id, '-y'],
                check=True
            )
            return True
        except Exception as e:
            print(f"Error updating app: {e}")
            return False
    
    def update_all_apps(self) -> bool:
        """Update all Flatpak applications"""
        try:
            subprocess.run(
                ['flatpak', 'update', '-y'],
                check=True
            )
            return True
        except Exception as e:
            print(f"Error updating all apps: {e}")
            return False

class IconLoader(QThread):
    """Thread for loading app icons"""
    icon_loaded = pyqtSignal(str, QPixmap)
    
    def __init__(self, app_id: str, icon_url: str):
        super().__init__()
        self.app_id = app_id
        self.icon_url = icon_url
    
    def run(self):
        try:
            req = Request(self.icon_url, headers={'User-Agent': 'Flatpakky/1.0'})
            with urlopen(req, timeout=10) as response:
                data = response.read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.icon_loaded.emit(self.app_id, pixmap)
        except Exception as e:
            print(f"Error loading icon for {self.app_id}: {e}")

class AppWorker(QThread):
    """Worker thread for app operations"""
    operation_finished = pyqtSignal(bool, str)
    progress_updated = pyqtSignal(str)
    
    def __init__(self, operation: str, app_id: str, api: FlatpakAPI):
        super().__init__()
        self.operation = operation
        self.app_id = app_id
        self.api = api
    
    def run(self):
        try:
            if self.operation == "install":
                self.progress_updated.emit(f"Installing {self.app_id}...")
                success = self.api.install_app(self.app_id)
                self.operation_finished.emit(success, "install")
            elif self.operation == "uninstall":
                self.progress_updated.emit(f"Uninstalling {self.app_id}...")
                success = self.api.uninstall_app(self.app_id)
                self.operation_finished.emit(success, "uninstall")
            elif self.operation == "update":
                self.progress_updated.emit(f"Updating {self.app_id}...")
                success = self.api.update_app(self.app_id)
                self.operation_finished.emit(success, "update")
            elif self.operation == "update_all":
                self.progress_updated.emit("Updating all applications...")
                success = self.api.update_all_apps()
                self.operation_finished.emit(success, "update_all")
        except Exception as e:
            self.operation_finished.emit(False, self.operation)

class BatchDownloadDialog(QDialog):
    """Dialog for batch downloading apps"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Download")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel("Enter Flatpak app IDs (one per line):")
        layout.addWidget(instructions)
        
        # Text area for app IDs
        self.app_ids_text = QTextEdit()
        self.app_ids_text.setPlaceholderText("com.example.App1\ncom.example.App2\ncom.example.App3")
        layout.addWidget(self.app_ids_text)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_app_ids(self) -> List[str]:
        """Get list of app IDs from the text area"""
        text = self.app_ids_text.toPlainText()
        app_ids = [line.strip() for line in text.split('\n') if line.strip()]
        return app_ids

class AdvancedSettingsDialog(QDialog):
    """Dialog for advanced settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout()
        
        # Flatpak remotes
        remotes_group = QGroupBox("Flatpak Remotes")
        remotes_layout = QVBoxLayout()
        
        self.remotes_tree = QTreeWidget()
        self.remotes_tree.setHeaderLabels(["Name", "URL", "Enabled"])
        remotes_layout.addWidget(self.remotes_tree)
        
        remotes_buttons = QHBoxLayout()
        add_remote_btn = QPushButton("Add Remote")
        remove_remote_btn = QPushButton("Remove Remote")
        remotes_buttons.addWidget(add_remote_btn)
        remotes_buttons.addWidget(remove_remote_btn)
        remotes_layout.addLayout(remotes_buttons)
        
        remotes_group.setLayout(remotes_layout)
        layout.addWidget(remotes_group)
        
        # Other settings
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout()
        
        settings_layout.addWidget(QLabel("Auto-update:"), 0, 0)
        self.auto_update_check = QCheckBox()
        settings_layout.addWidget(self.auto_update_check, 0, 1)
        
        settings_layout.addWidget(QLabel("Parallel downloads:"), 1, 0)
        self.parallel_downloads = QSpinBox()
        self.parallel_downloads.setRange(1, 10)
        self.parallel_downloads.setValue(3)
        settings_layout.addWidget(self.parallel_downloads, 1, 1)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        self.load_remotes()
    
    def load_remotes(self):
        """Load Flatpak remotes"""
        try:
            result = subprocess.run(
                ['flatpak', 'remotes', '--columns=name,url,options'],
                capture_output=True, text=True, check=True
            )
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        item = QTreeWidgetItem([parts[0], parts[1], "Yes" if "disabled" not in parts[2] else "No"])
                        self.remotes_tree.addTopLevelItem(item)
        except Exception as e:
            print(f"Error loading remotes: {e}")

class FlatpakkyMainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.api = FlatpakAPI()
        self.current_apps = []
        self.installed_apps = []
        self.selected_app = None
        self.icon_loaders = []
        self.app_icons = {}
        
        self.init_ui()
        self.load_installed_apps()
        self.load_apps()
        
        # Set up timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start(300000)  # Check every 5 minutes
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Flatpakky - Flathub Browser")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set application icon
        self.setWindowIcon(QIcon())
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Title
        title_label = QLabel("FLATPAKKY")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Search bar
        search_icon = QLabel("🔍")
        header_layout.addWidget(search_icon)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Flathub")
        self.search_bar.returnPressed.connect(self.search_apps)
        header_layout.addWidget(self.search_bar)
        
        main_layout.addLayout(header_layout)
        
        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Browse Applications
        browse_label = QLabel("Browse Applications")
        browse_font = QFont()
        browse_font.setBold(True)
        browse_label.setFont(browse_font)
        left_layout.addWidget(browse_label)
        
        # App list
        self.app_list = QListWidget()
        self.app_list.itemSelectionChanged.connect(self.on_app_selected)
        left_layout.addWidget(self.app_list)
        
        # Categories
        categories_label = QLabel("Categories")
        categories_font = QFont()
        categories_font.setBold(True)
        categories_label.setFont(categories_font)
        left_layout.addWidget(categories_label)
        
        self.categories_list = QListWidget()
        categories = [
            "All Apps", "Audio & Video", "Development", "Education",
            "Games", "Graphics & Photography", "Internet", "Office",
            "Science", "System", "Utilities"
        ]
        for category in categories:
            self.categories_list.addItem(category)
        self.categories_list.itemClicked.connect(self.on_category_selected)
        left_layout.addWidget(self.categories_list)
        
        main_splitter.addWidget(left_panel)
        
        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # App details
        details_label = QLabel("App Details")
        details_font = QFont()
        details_font.setBold(True)
        details_label.setFont(details_font)
        right_layout.addWidget(details_label)
        
        # App details frame
        self.details_frame = QFrame()
        self.details_frame.setFrameStyle(QFrame.Shape.Box)
        details_layout = QVBoxLayout()
        self.details_frame.setLayout(details_layout)
        
        # App icon
        self.app_icon = QLabel()
        self.app_icon.setFixedSize(64, 64)
        self.app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.app_icon.setStyleSheet("border: 1px solid gray;")
        details_layout.addWidget(self.app_icon)
        
        # App info
        self.app_name = QLabel("Select an app")
        self.app_name.setFont(QFont("", 14, QFont.Weight.Bold))
        details_layout.addWidget(self.app_name)
        
        self.app_version = QLabel("")
        details_layout.addWidget(self.app_version)
        
        self.app_description = QTextEdit()
        self.app_description.setMaximumHeight(100)
        self.app_description.setReadOnly(True)
        details_layout.addWidget(self.app_description)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        self.install_button = QPushButton("Install")
        self.install_button.clicked.connect(self.install_app)
        self.install_button.setEnabled(False)
        buttons_layout.addWidget(self.install_button)
        
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.uninstall_app)
        self.remove_button.setEnabled(False)
        buttons_layout.addWidget(self.remove_button)
        
        details_layout.addLayout(buttons_layout)
        
        right_layout.addWidget(self.details_frame)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self.update_all_apps)
        controls_layout.addWidget(self.update_button)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_apps)
        controls_layout.addWidget(self.refresh_button)
        
        self.advanced_button = QPushButton("Advanced...")
        self.advanced_button.clicked.connect(self.show_advanced_settings)
        controls_layout.addWidget(self.advanced_button)
        
        right_layout.addLayout(controls_layout)
        
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setSizes([300, 500])
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.update_status()
        
        # Create menu bar
        self.create_menu_bar()
    
    def create_menu_bar(self):
        """Create menu bar with various options"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        # Batch download action
        batch_action = QAction('Batch Download...', self)
        batch_action.triggered.connect(self.show_batch_download)
        file_menu.addAction(batch_action)
        
        # Install from file action
        install_file_action = QAction('Install from .flatpakref...', self)
        install_file_action.triggered.connect(self.install_from_file)
        file_menu.addAction(install_file_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        # Donation action
        donate_action = QAction('Donate ❤️', self)
        donate_action.triggered.connect(lambda: webbrowser.open('https://www.ko-fi.com/MalikHw47'))
        help_menu.addAction(donate_action)
        
        # YouTube action
        youtube_action = QAction('YouTube Channel 📺', self)
        youtube_action.triggered.connect(lambda: webbrowser.open('https://youtube.com/@malikhw47?si=f7ksxEDBKZ5sCpqj'))
        help_menu.addAction(youtube_action)
        
        # GitHub action
        github_action = QAction('GitHub 🐙', self)
        github_action.triggered.connect(lambda: webbrowser.open('https://github.com/MalikHw'))
        help_menu.addAction(github_action)
        
        help_menu.addSeparator()
        
        # About action
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def load_apps(self, query: str = ""):
        """Load apps from Flathub"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_bar.showMessage("Loading applications...")
        
        # Load apps in a separate thread
        def load_apps_thread():
            apps = self.api.search_apps(query)
            self.current_apps = apps
            
            # Update UI in main thread
            QApplication.instance().processEvents()
            self.app_list.clear()
            
            for app in apps:
                item = QListWidgetItem()
                item.setText(app.get('name', app.get('flatpakAppId', 'Unknown')))
                item.setData(Qt.ItemDataRole.UserRole, app)
                self.app_list.addItem(item)
                
                # Load icon if available
                if 'icon' in app:
                    self.load_app_icon(app['flatpakAppId'], app['icon'])
            
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage("Ready")
        
        # Run in thread
        thread = threading.Thread(target=load_apps_thread)
        thread.daemon = True
        thread.start()
    
    def load_installed_apps(self):
        """Load installed applications"""
        self.installed_apps = self.api.get_installed_apps()
        self.update_status()
    
    def load_app_icon(self, app_id: str, icon_url: str):
        """Load app icon asynchronously"""
        if app_id in self.app_icons:
            return
        
        icon_loader = IconLoader(app_id, icon_url)
        icon_loader.icon_loaded.connect(self.on_icon_loaded)
        icon_loader.start()
        self.icon_loaders.append(icon_loader)
    
    def on_icon_loaded(self, app_id: str, pixmap: QPixmap):
        """Handle icon loaded signal"""
        self.app_icons[app_id] = pixmap
        
        # Update current app display if it matches
        if self.selected_app and self.selected_app.get('flatpakAppId') == app_id:
            self.app_icon.setPixmap(pixmap)
    
    def search_apps(self):
        """Search for apps"""
        query = self.search_bar.text().strip()
        self.load_apps(query)
    
    def on_app_selected(self):
        """Handle app selection"""
        current_item = self.app_list.currentItem()
        if current_item:
            app_data = current_item.data(Qt.ItemDataRole.UserRole)
            self.selected_app = app_data
            self.update_app_details()
    
    def on_category_selected(self, item):
        """Handle category selection"""
        category = item.text()
        if category == "All Apps":
            self.load_apps()
        else:
            # For now, just load all apps (category filtering would need more API work)
            self.load_apps()
    
    def update_app_details(self):
        """Update app details panel"""
        if not self.selected_app:
            return
        
        app = self.selected_app
        app_id = app.get('flatpakAppId', '')
        
        # Update app info
        self.app_name.setText(app.get('name', app_id))
        self.app_version.setText(f"Version: {app.get('currentReleaseVersion', 'Unknown')}")
        self.app_description.setPlainText(app.get('summary', 'No description available'))
        
        # Update app icon
        if app_id in self.app_icons:
            self.app_icon.setPixmap(self.app_icons[app_id])
        else:
            self.app_icon.clear()
            self.app_icon.setText("No Icon")
            if 'icon' in app:
                self.load_app_icon(app_id, app['icon'])
        
        # Update buttons
        is_installed = any(installed['flatpakAppId'] == app_id for installed in self.installed_apps)
        self.install_button.setEnabled(not is_installed)
        self.remove_button.setEnabled(is_installed)
        
        if is_installed:
            self.install_button.setText("Installed")
        else:
            self.install_button.setText("Install")
    
    def install_app(self):
        """Install selected app"""
        if not self.selected_app:
            return
        
        app_id = self.selected_app.get('flatpakAppId', '')
        if not app_id:
            return
        
        # Disable buttons
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        
        # Start installation
        self.worker = AppWorker("install", app_id, self.api)
        self.worker.operation_finished.connect(self.on_operation_finished)
        self.worker.progress_updated.connect(self.status_bar.showMessage)
        self.worker.start()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
    
    def uninstall_app(self):
        """Uninstall selected app"""
        if not self.selected_app:
            return
        
        app_id = self.selected_app.get('flatpakAppId', '')
        if not app_id:
            return
        
        # Confirm uninstall
        reply = QMessageBox.question(
            self, 'Confirm Uninstall',
            f'Are you sure you want to uninstall {self.selected_app.get("name", app_id)}?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Disable buttons
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        
        # Start uninstallation
        self.worker = AppWorker("uninstall", app_id, self.api)
        self.worker.operation_finished.connect(self.on_operation_finished)
        self.worker.progress_updated.connect(self.status_bar.showMessage)
        self.worker.start()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
    
    def update_all_apps(self):
        """Update all installed apps"""
        self.worker = AppWorker("update_all", "", self.api)
        self.worker.operation_finished.connect(self.on_operation_finished)
        self.worker.progress_updated.connect(self.status_bar.showMessage)
        self.worker.start()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
    
    def on_operation_finished(self, success: bool, operation: str):
        """Handle operation completion"""
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_bar.showMessage(f"Operation completed successfully", 3000)
            self.load_installed_apps()
            self.update_app_details()
        else:
            self.status_bar.showMessage(f"Operation failed", 3000)
            QMessageBox.warning(self, "Operation Failed", f"The {operation} operation failed. Please check your internet connection and try again.")
        
        # Re-enable buttons
        if hasattr(self, 'selected_app') and self.selected_app:
            self.update_app_details()
    
    def refresh_apps(self):
        """Refresh app list"""
        self.load_apps()
        self.load_installed_apps()
    
    def show_advanced_settings(self):
        """Show advanced settings dialog"""
        dialog = AdvancedSettingsDialog(self)
        dialog.exec()
    
    def show_batch_download(self):
        """Show batch download dialog"""
        dialog = BatchDownloadDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            app_ids = dialog.get_app_ids()
            if app_ids:
                self.batch_install_apps(app_ids)
    
    def batch_install_apps(self, app_ids: List[str]):
        """Install multiple apps in batch"""
        def install_batch():
            for app_id in app_ids:
                self.status_bar.showMessage(f"Installing {app_id}...")
                self.api.install_app(app_id)
            
            self.status_bar.showMessage("Batch installation completed")
            self.load_installed_apps()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        thread = threading.Thread(target=install_batch)
        thread.daemon = True
        thread.start()
    
    def install_from_file(self):
        """Install app from .flatpakref file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Flatpakref File", "", "Flatpakref Files (*.flatpakref)"
        )
        
        if file_path:
            try:
                subprocess.run(['flatpak', 'install', file_path, '-y'], check=True)
                self.status_bar.showMessage("Installation from file completed", 3000)
                self.load_installed_apps()
            except Exception as e:
                QMessageBox.warning(self, "Installation Failed", f"Failed to install from file: {str(e)}")
    
    def check_for_updates(self):
        """Check for available updates"""
        try:
            result = subprocess.run(
                ['flatpak', 'remote-ls', '--updates'],
                capture_output=True, text=True, check=True
            )
            updates = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            self.update_status(updates)
        except Exception:
            pass
    
    def update_status(self, updates: int = 0):
        """Update status bar"""
        installed_count = len(self.installed_apps)
        if updates > 0:
            self.status_bar.showMessage(f"Status: Ready | {installed_count} apps installed | {updates} updates available")
        else:
            self.status_bar.showMessage(f"Status: Ready | {installed_count} apps installed")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About Flatpakky",
            "Flatpakky v1.0\n\n"
            "A Flathub-like browser for Flatpaks\n"
            "Created by MalikHw47\n\n"
            "Features:\n"
            "• Browse and search Flathub applications\n"
            "• Install and uninstall Flatpak packages\n"
            "• Batch downloading support\n"
            "• .flatpakref file support\n"
            "• Icon and category support\n\n"
            "Support the developer:\n"
            "• Ko-fi: https://www.ko-fi.com/MalikHw47\n"
            "• YouTube: https://youtube.com/@malikhw47\n"
            "• GitHub: https://github.com/MalikHw"
        )
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop all icon loaders
        for loader in self.icon_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        
        # Stop timer
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        event.accept()

class FlatpakkyApp(QApplication):
    """Main application class"""
    
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("Flatpakky")
        self.setApplicationVersion("1.0")
        self.setOrganizationName("MalikHw47")
        
        # Set application style
        self.setStyle('Fusion')
        
        # Handle .flatpakref files
        if len(argv) > 1 and argv[1].endswith('.flatpakref'):
            self.flatpakref_file = argv[1]
        else:
            self.flatpakref_file = None
        
        # Create main window
        self.main_window = FlatpakkyMainWindow()
        self.main_window.show()
        
        # Handle flatpakref file if provided
        if self.flatpakref_file:
            self.handle_flatpakref_file()
    
    def handle_flatpakref_file(self):
        """Handle .flatpakref file passed as argument"""
        reply = QMessageBox.question(
            self.main_window, 'Install Application',
            f'Do you want to install the application from {self.flatpakref_file}?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                subprocess.run(['flatpak', 'install', self.flatpakref_file, '-y'], check=True)
                QMessageBox.information(self.main_window, "Success", "Application installed successfully!")
                self.main_window.load_installed_apps()
            except Exception as e:
                QMessageBox.warning(self.main_window, "Installation Failed", f"Failed to install: {str(e)}")

def main():
    """Main entry point"""
    import sys
    
    # Check if flatpak is available
    try:
        subprocess.run(['flatpak', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Flatpak is not installed or not available in PATH")
        print("Please install Flatpak first:")
        print("  Ubuntu/Debian: sudo apt install flatpak")
        print("  Fedora: sudo dnf install flatpak")
        print("  Arch: sudo pacman -S flatpak")
        sys.exit(1)
    
    # Create and run application
    app = FlatpakkyApp(sys.argv)
    
    # Set up MIME type handling for .flatpakref files
    try:
        # Create .desktop file for MIME type association
        desktop_file_content = """[Desktop Entry]
Name=Flatpakky
Comment=Flathub browser for Flatpaks
Exec=python3 {script_path} %f
Icon=application-x-flatpakref
Terminal=false
Type=Application
MimeType=application/vnd.flatpak.ref;
Categories=System;PackageManager;
""".format(script_path=os.path.abspath(__file__))
        
        desktop_dir = os.path.expanduser("~/.local/share/applications")
        os.makedirs(desktop_dir, exist_ok=True)
        
        with open(os.path.join(desktop_dir, "flatpakky.desktop"), 'w') as f:
            f.write(desktop_file_content)
        
        # Update MIME database
        subprocess.run(['update-desktop-database', desktop_dir], capture_output=True)
        
    except Exception as e:
        print(f"Warning: Could not set up MIME type association: {e}")
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()