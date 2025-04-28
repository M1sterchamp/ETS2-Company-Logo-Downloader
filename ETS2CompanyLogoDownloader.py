import sys
import os
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel,
    QFileDialog, QProgressBar, QMessageBox, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class LogoDownloaderWorker(QThread):
    progress = pyqtSignal(int)
    status_update = pyqtSignal(str)

    def __init__(self, url, save_folder):
        super().__init__()
        self.url = url
        self.save_folder = save_folder
        self.is_running = True

    def run(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            images = soup.find_all("img")

            total_images = len(images)
            if total_images == 0:
                self.status_update.emit("No images found on the page.")
                return

            logos_folder = os.path.join(self.save_folder, "Downloaded_Company_Logos")
            os.makedirs(logos_folder, exist_ok=True)

            self.progress.emit(0)
            count = 0

            for idx, img in enumerate(images):
                if not self.is_running:
                    self.status_update.emit("Download canceled.")
                    return

                img_url = img.get("data-src") or img.get("src")
                if not img_url:
                    continue
                if img_url.startswith("data:image"):
                    continue
                if '/images/' not in img_url:
                    continue

                full_size_url = img_url.split("/revision/")[0]

                try:
                    img_data = requests.get(full_size_url).content
                    if len(img_data) < 5000:
                        continue
                except Exception:
                    continue

                img_name = os.path.basename(full_size_url)
                if not img_name or "." not in img_name:
                    img_name = f"logo_{idx}.jpg"

                img_name = "".join(c for c in img_name if c.isalnum() or c in (' ', '.', '_')).rstrip()
                save_path = os.path.join(logos_folder, img_name)

                try:
                    with open(save_path, "wb") as f:
                        f.write(img_data)
                    count += 1
                except Exception:
                    continue

                progress_percent = int(((idx + 1) / total_images) * 100)
                self.progress.emit(progress_percent)

            self.progress.emit(100)
            self.status_update.emit(f"Downloaded {count} logos to 'Downloaded_Company_Logos'.")
        except requests.exceptions.RequestException as e:
            self.status_update.emit(f"Network Error: {str(e)}")
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")

    def stop(self):
        self.is_running = False

class FullSizeLogoDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ETS2 Company Logo Downloader")
        self.setFixedSize(500, 400)
        
        # Fancy styles
        self.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 12px;
                font-weight: bold;
                border-radius: 8px;
            }
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
            QProgressBar {
                height: 25px;
                border: 1px solid #aaa;
                border-radius: 8px;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                border-radius: 8px;
            }
        """)

        # Fix background to white
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(p)

        self.init_ui()
        self.fade_in_animation()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)

        self.select_folder_btn = QPushButton("Select Save Folder", self)
        self.select_folder_btn.setStyleSheet("background-color: #3498db; color: white;")
        self.select_folder_btn.clicked.connect(self.select_folder)
        layout.addWidget(self.select_folder_btn)

        self.download_btn = QPushButton("Download Logos", self)
        self.download_btn.setStyleSheet("background-color: #2ecc71; color: white;")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("Cancel Download", self)
        self.cancel_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Waiting...", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        self.save_folder = ""
        self.worker = None
        self.url = "https://truck-simulator.fandom.com/wiki/Euro_Truck_Simulator_2_Companies"
        self.animation = None

    def fade_in_animation(self):
        opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_effect)

        self.fade_animation = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_animation.setDuration(800)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.start()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.save_folder = folder
            self.status_label.setText("Selected save folder.")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")

    def start_download(self):
        if not self.save_folder:
            QMessageBox.warning(self, "No Folder", "Please select a save folder first!")
            return

        self.worker = LogoDownloaderWorker(self.url, self.save_folder)
        self.worker.progress.connect(self.animate_progress)
        self.worker.status_update.connect(self.update_status)
        self.worker.start()

        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Status: Downloading...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12;")

    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.status_label.setText("Status: Download canceled.")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;")
            self.progress_bar.setValue(0)
            self.download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def animate_progress(self, value):
        if self.animation:
            self.animation.stop()

        self.animation = QPropertyAnimation(self.progress_bar, b"value")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.progress_bar.value())
        self.animation.setEndValue(value)
        self.animation.start()

    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")
        if "Downloaded" in message:
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2ecc71;")
        elif "canceled" in message.lower():
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;")
        else:
            self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")

        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FullSizeLogoDownloader()
    window.show()
    sys.exit(app.exec())
