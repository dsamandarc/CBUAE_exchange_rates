import os
import sys
import subprocess
import platform
import requests
import zipfile
import stat
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChromeDriverInstaller:
    """
    A comprehensive ChromeDriver installer with modern features and robust error handling.
    """
    
    # Chrome for Testing API endpoints (modern approach)
    CHROME_FOR_TESTING_API = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    LEGACY_API = "https://chromedriver.storage.googleapis.com/LATEST_RELEASE"
    
    # Platform mappings
    PLATFORM_MAPPING = {
        'linux': {
            'x86_64': 'linux64',
            'amd64': 'linux64',
            'i386': 'linux32',
            'i686': 'linux32'
        },
        'darwin': {
            'x86_64': 'mac-x64',
            'arm64': 'mac-arm64'
        },
        'windows': {
            'amd64': 'win64',
            'x86_64': 'win64',
            'i386': 'win32'
        }
    }
    
    # Required Python packages
    REQUIRED_PACKAGES = [
        'selenium>=4.15.0',
        'webdriver-manager>=4.0.0',
        'requests>=2.25.0',
        'beautifulsoup4>=4.9.0'
    ]
    
    def __init__(self, verbose: bool = True):
        """
        Initialize the ChromeDriver installer.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()
        self.temp_dir = tempfile.mkdtemp(prefix='chromedriver_install_')
        
        if verbose:
            print("ChromeDriver Automatic Installer - Optimized Version")
            print(f"System: {self.system} ({self.machine})")
            print(f"Python: {sys.version.split()[0]}")
            print(f"Temp directory: {self.temp_dir}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def get_platform_identifier(self) -> Optional[str]:
        """
        Get the platform identifier for ChromeDriver downloads.
        
        Returns:
            Platform identifier string or None if unsupported
        """
        if self.system not in self.PLATFORM_MAPPING:
            logger.error(f"Unsupported system: {self.system}")
            return None
        
        platform_variants = self.PLATFORM_MAPPING[self.system]
        
        # Try exact match first
        if self.machine in platform_variants:
            return platform_variants[self.machine]
        
        # Fallback logic
        if self.system == 'linux':
            return 'linux64' if '64' in self.machine else 'linux32'
        elif self.system == 'darwin':
            return 'mac-arm64' if 'arm' in self.machine else 'mac-x64'
        elif self.system == 'windows':
            return 'win64' if '64' in self.machine else 'win32'
        
        return None
    
    def get_chrome_version(self) -> Optional[str]:
        """
        Detect installed Chrome version.
        
        Returns:
            Chrome version string or None if not found
        """
        chrome_commands = {
            'linux': [
                ['google-chrome', '--version'],
                ['chromium-browser', '--version'],
                ['chromium', '--version']
            ],
            'darwin': [
                ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'],
                ['/Applications/Chromium.app/Contents/MacOS/Chromium', '--version']
            ],
            'windows': [
                ['chrome.exe', '--version'],
                ['chromium.exe', '--version']
            ]
        }
        
        commands = chrome_commands.get(self.system, [])
        
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    version_line = result.stdout.strip()
                    # Extract version number (e.g., "Google Chrome 120.0.6099.109" -> "120.0.6099.109")
                    version = version_line.split()[-1]
                    if self.verbose:
                        print(f"🔍 Detected Chrome version: {version}")
                    return version
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                continue
        
        if self.verbose:
            print("Chrome version not detected, will use latest stable")
        return None
    
    def get_compatible_chromedriver_version(self) -> Tuple[str, str]:
        """
        Get compatible ChromeDriver version and download URL.
        
        Returns:
            Tuple of (version, download_url)
        """
        chrome_version = self.get_chrome_version()
        platform_id = self.get_platform_identifier()
        
        if not platform_id:
            raise ValueError(f"Unsupported platform: {self.system} {self.machine}")
        
        # Try modern Chrome for Testing API first
        try:
            if self.verbose:
                print("Checking Chrome for Testing API...")
            
            response = requests.get(self.CHROME_FOR_TESTING_API, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            versions = data.get('versions', [])
            
            # Find compatible version
            target_version = None
            download_url = None
            
            if chrome_version:
                # Find exact or closest match
                chrome_major = chrome_version.split('.')[0]
                for version_info in reversed(versions):  # Start from latest
                    version = version_info.get('version', '')
                    if version.startswith(chrome_major):
                        # Look for ChromeDriver download
                        downloads = version_info.get('downloads', {})
                        chromedriver_downloads = downloads.get('chromedriver', [])
                        
                        for download in chromedriver_downloads:
                            if download.get('platform') == platform_id:
                                target_version = version
                                download_url = download.get('url')
                                break
                        
                        if target_version:
                            break
            
            # If no specific match, get latest stable
            if not target_version and versions:
                latest_version = versions[-1]
                version = latest_version.get('version', '')
                downloads = latest_version.get('downloads', {})
                chromedriver_downloads = downloads.get('chromedriver', [])
                
                for download in chromedriver_downloads:
                    if download.get('platform') == platform_id:
                        target_version = version
                        download_url = download.get('url')
                        break
            
            if target_version and download_url:
                if self.verbose:
                    print(f"Found compatible version: {target_version}")
                return target_version, download_url
                
        except Exception as e:
            logger.warning(f"Chrome for Testing API failed: {e}")
        
        # Fallback to legacy API
        try:
            if self.verbose:
                print("Falling back to legacy API...")
            
            response = requests.get(self.LEGACY_API, timeout=30)
            response.raise_for_status()
            
            version = response.text.strip()
            download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_{platform_id}.zip"
            
            if self.verbose:
                print(f"Using legacy version: {version}")
            
            return version, download_url
            
        except Exception as e:
            logger.error(f"Legacy API also failed: {e}")
            raise RuntimeError("Unable to determine ChromeDriver version")
    
    def download_and_extract(self, download_url: str, version: str) -> str:
        """
        Download and extract ChromeDriver.
        
        Args:
            download_url: URL to download ChromeDriver
            version: Version being downloaded
            
        Returns:
            Path to extracted ChromeDriver executable
        """
        if self.verbose:
            print(f"⬇Downloading ChromeDriver {version}...")
            print(f"URL: {download_url}")
        
        # Download
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()
        
        zip_path = os.path.join(self.temp_dir, "chromedriver.zip")
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        if self.verbose:
            print("Extracting archive...")
        
        # Extract
        extract_dir = os.path.join(self.temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find ChromeDriver executable
        chromedriver_name = "chromedriver.exe" if self.system == "windows" else "chromedriver"
        
        # Search for the executable (might be in subdirectories)
        for root, dirs, files in os.walk(extract_dir):
            if chromedriver_name in files:
                chromedriver_path = os.path.join(root, chromedriver_name)
                
                # Make executable on Unix systems
                if self.system in ["linux", "darwin"]:
                    os.chmod(chromedriver_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                
                return chromedriver_path
        
        raise FileNotFoundError("ChromeDriver executable not found in archive")
    
    def install_to_system(self, chromedriver_path: str) -> bool:
        """
        Install ChromeDriver to system PATH.
        
        Args:
            chromedriver_path: Path to ChromeDriver executable
            
        Returns:
            True if successful, False otherwise
        """
        if self.verbose:
            print("Installing ChromeDriver to system PATH...")
        
        target_locations = {
            'linux': ['/usr/local/bin', '/usr/bin'],
            'darwin': ['/usr/local/bin', '/opt/homebrew/bin'],
            'windows': [os.path.expandvars(r'%PROGRAMFILES%\ChromeDriver')]
        }
        
        locations = target_locations.get(self.system, [])
        
        for location in locations:
            try:
                if not os.path.exists(location):
                    if self.system == 'windows':
                        os.makedirs(location, exist_ok=True)
                    else:
                        continue
                
                target_name = "chromedriver.exe" if self.system == "windows" else "chromedriver"
                target_path = os.path.join(location, target_name)
                
                if self.system == "windows":
                    shutil.copy2(chromedriver_path, target_path)
                else:
                    subprocess.run(['sudo', 'cp', chromedriver_path, target_path], check=True)
                    subprocess.run(['sudo', 'chmod', '+x', target_path], check=True)
                
                if self.verbose:
                    print(f"ChromeDriver installed to: {target_path}")
                
                return True
                
            except (subprocess.CalledProcessError, PermissionError, OSError) as e:
                logger.debug(f"Failed to install to {location}: {e}")
                continue
        
        # If system installation fails, try user directory
        try:
            user_bin = os.path.expanduser("~/.local/bin")
            os.makedirs(user_bin, exist_ok=True)
            
            target_name = "chromedriver.exe" if self.system == "windows" else "chromedriver"
            target_path = os.path.join(user_bin, target_name)
            
            shutil.copy2(chromedriver_path, target_path)
            
            if self.system != "windows":
                os.chmod(target_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            if self.verbose:
                print(f"ChromeDriver installed to user directory: {target_path}")
                print("Make sure ~/.local/bin is in your PATH")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to install to user directory: {e}")
            return False
    
    def install_via_package_manager(self) -> bool:
        """
        Try to install ChromeDriver via system package manager.
        
        Returns:
            True if successful, False otherwise
        """
        if self.verbose:
            print("Attempting package manager installation...")
        
        package_commands = {
            'linux': [
                ['sudo', 'apt-get', 'update'],
                ['sudo', 'apt-get', 'install', '-y', 'chromium-browser', 'chromium-chromedriver']
            ],
            'darwin': [
                ['brew', 'install', 'chromedriver']
            ]
        }
        
        commands = package_commands.get(self.system, [])
        
        for cmd in commands:
            try:
                if self.verbose:
                    print(f"Running: {' '.join(cmd)}")
                
                subprocess.run(cmd, check=True, capture_output=True)
                
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.debug(f"Package manager command failed: {e}")
                return False
        
        # Verify installation
        try:
            result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                if self.verbose:
                    print(f"Package manager installation successful: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        return False
    
    def install_python_dependencies(self) -> bool:
        """
        Install required Python packages.
        
        Returns:
            True if successful, False otherwise
        """
        if self.verbose:
            print("Installing Python dependencies...")
        
        success = True
        
        for package in self.REQUIRED_PACKAGES:
            try:
                if self.verbose:
                    print(f"Installing {package}...")
                
                subprocess.run([
                    sys.executable, '-m', 'pip', 'install', '--upgrade', package
                ], check=True, capture_output=True)
                
                if self.verbose:
                    print(f"{package} installed successfully")
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {package}: {e}")
                success = False
        
        return success
    
    def verify_installation(self) -> bool:
        """
        Verify ChromeDriver installation by running a test.
        
        Returns:
            True if verification successful, False otherwise
        """
        if self.verbose:
            print("Verifying ChromeDriver installation...")
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            # Configure Chrome options
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            
            # Try different initialization methods
            driver = None
            
            # Method 1: System ChromeDriver
            try:
                driver = webdriver.Chrome(options=options)
            except Exception:
                # Method 2: WebDriver Manager
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                except Exception:
                    pass
            
            if not driver:
                return False
            
            # Test basic functionality
            driver.get('https://www.google.com')
            title = driver.title
            driver.quit()
            
            if self.verbose:
                print(f"ChromeDriver verification successful! (Test page title: {title})")
            
            return True
            
        except Exception as e:
            logger.error(f"ChromeDriver verification failed: {e}")
            return False
    
    def install(self) -> bool:
        """
        Main installation method that tries multiple approaches.
        
        Returns:
            True if installation successful, False otherwise
        """
        installation_methods = [
            ("Package Manager", self.install_via_package_manager),
            ("Manual Download", self._install_manual),
        ]
        
        # Install Python dependencies first
        if not self.install_python_dependencies():
            logger.warning("Some Python dependencies failed to install")
        
        # Try installation methods
        for method_name, method_func in installation_methods:
            try:
                if self.verbose:
                    print(f"\n🔄 Trying {method_name} installation...")
                
                if method_func():
                    if self.verify_installation():
                        if self.verbose:
                            print(f"🎉 {method_name} installation successful!")
                        return True
                    else:
                        if self.verbose:
                            print(f"{method_name} installation completed but verification failed")
                
            except Exception as e:
                logger.error(f"{method_name} installation failed: {e}")
                continue
        
        return False
    
    def _install_manual(self) -> bool:
        """
        Manual installation method.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            version, download_url = self.get_compatible_chromedriver_version()
            chromedriver_path = self.download_and_extract(download_url, version)
            return self.install_to_system(chromedriver_path)
        except Exception as e:
            logger.error(f"Manual installation failed: {e}")
            return False


def main():
    """Main function to run the ChromeDriver installer."""
    
    try:
        with ChromeDriverInstaller(verbose=True) as installer:
            success = installer.install()
            
            if success:
                print("CHROMEDRIVER INSTALLATION COMPLETED SUCCESSFULLY!")
                print("ChromeDriver is ready to use")
                print("Python dependencies installed")
                print("Installation verified")
                print("You can now run your CBUAE extractor:")
                print("python3 cbuae_extractor.py")
                
            else:
                print("CHROMEDRIVER INSTALLATION FAILED")
                print("💡 Manual installation options:")
                print("   - Ubuntu/Debian: sudo apt install chromium-chromedriver")
                print("   - macOS: brew install chromedriver")
                print("   - Windows: Download from https://chromedriver.chromium.org/")
                print("   - Use WebDriver Manager in your code")
                
                return 1
                
    except KeyboardInterrupt:
        print("Installation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())