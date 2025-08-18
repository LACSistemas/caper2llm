from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, UnexpectedAlertPresentException
from selenium.webdriver.support.ui import Select
import time
import os
import re
import glob
import json
from pathlib import Path

class PJEAutomationOptimized:
    def __init__(self, headless=False):
        """Initialize the PJE automation system with improved download handling"""
        self.driver = None
        self.wait = None
        self.headless = headless
        self.original_window = None
        
        # Create a unique session folder for this run
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_folder = f"session_{timestamp}"
        self.download_dir = os.path.join(os.getcwd(), "downloads", self.session_folder)
        self.temp_download_dir = os.path.join(os.getcwd(), "temp_downloads")
        
        print(f"📁 Session download folder: {self.download_dir}")
        
    def setup_driver(self):
        """Setup Firefox driver with optimized download configuration"""
        firefox_options = Options()
        if self.headless:
            firefox_options.add_argument("--headless")
        
        # Create download directories
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_download_dir, exist_ok=True)
        
        # Clear temp directory
        self._clear_directory(self.temp_download_dir)
        
        # Configure Firefox profile for automatic downloads
        firefox_options.set_preference("browser.download.folderList", 2)
        firefox_options.set_preference("browser.download.dir", self.temp_download_dir)
        firefox_options.set_preference("browser.download.useDownloadDir", True)
        firefox_options.set_preference("browser.download.viewableInternally.enabledTypes", "")
        firefox_options.set_preference("browser.helperApps.neverAsk.saveToDisk", 
                                     "application/pdf,application/x-pdf,application/acrobat,applications/vnd.pdf,"
                                     "text/pdf,text/x-pdf,application/zip,application/octet-stream,"
                                     "application/x-zip-compressed,multipart/x-zip")
        firefox_options.set_preference("browser.helperApps.neverAsk.openFile", 
                                     "application/pdf,application/x-pdf,application/acrobat,applications/vnd.pdf,"
                                     "text/pdf,text/x-pdf")
        firefox_options.set_preference("browser.download.manager.showWhenStarting", False)
        firefox_options.set_preference("browser.download.manager.alertOnEXEOpen", False)
        firefox_options.set_preference("browser.download.manager.focusWhenStarting", False)
        firefox_options.set_preference("browser.download.manager.useWindow", False)
        firefox_options.set_preference("browser.download.manager.showAlertOnComplete", False)
        firefox_options.set_preference("browser.download.manager.closeWhenDone", False)
        firefox_options.set_preference("pdfjs.disabled", True)
        firefox_options.set_preference("plugin.scan.plid.all", False)
        firefox_options.set_preference("plugin.scan.Acrobat", "99.0")
        
        # Additional preferences for handling downloads
        firefox_options.set_preference("browser.helperApps.alwaysAsk.force", False)
        firefox_options.set_preference("browser.download.panel.shown", False)
        firefox_options.set_preference("browser.download.alwaysOpenPanel", False)
        firefox_options.set_preference("browser.download.manager.addToRecentDocs", False)
        
        print("🚀 Starting Firefox browser with optimized download settings...")
        self.driver = webdriver.Firefox(options=firefox_options)
        self.wait = WebDriverWait(self.driver, 30)
        self.driver.maximize_window()
        
        # Store the original window handle
        self.original_window = self.driver.current_window_handle
        
        # Set page load timeout
        self.driver.set_page_load_timeout(60)
        
    def _clear_directory(self, directory):
        """Clear all files in a directory"""
        try:
            files = glob.glob(os.path.join(directory, '*'))
            for f in files:
                if os.path.isfile(f):
                    os.remove(f)
        except Exception as e:
            print(f"⚠️ Error clearing directory: {str(e)}")
    
    def _get_download_files(self):
        """Get list of files in temp download directory"""
        try:
            return [f for f in os.listdir(self.temp_download_dir) 
                   if os.path.isfile(os.path.join(self.temp_download_dir, f))]
        except:
            return []
    
    def _wait_for_download_complete(self, timeout=120, initial_files=None):
        """Wait for download to complete with improved detection"""
        print("⏳ Monitoring download progress...")
        
        if initial_files is None:
            initial_files = set(self._get_download_files())
        
        start_time = time.time()
        download_started = False
        completed_files = []
        
        while (time.time() - start_time) < timeout:
            current_files = set(self._get_download_files())
            new_files = current_files - initial_files
            
            if new_files:
                download_started = True
                
                # Check each new file
                for filename in new_files:
                    filepath = os.path.join(self.temp_download_dir, filename)
                    
                    # Skip temporary files
                    if filename.endswith('.part') or filename.endswith('.crdownload') or filename.endswith('.tmp'):
                        print(f"⏳ Downloading: {filename}")
                        continue
                    
                    # Skip if already processed
                    if filename in initial_files:
                        continue
                    
                    # Check if file is still being written
                    try:
                        initial_size = os.path.getsize(filepath)
                        time.sleep(1)
                        current_size = os.path.getsize(filepath)
                        
                        if initial_size == current_size and current_size > 0:
                            # File size stable and not empty
                            print(f"✅ Download completed: {filename} ({current_size:,} bytes)")
                            
                            # Move to final download directory with overwrite handling
                            final_path = os.path.join(self.download_dir, filename)
                            
                            # If file already exists, create a unique name
                            if os.path.exists(final_path):
                                base_name, ext = os.path.splitext(filename)
                                counter = 1
                                while os.path.exists(final_path):
                                    new_filename = f"{base_name}_{counter}{ext}"
                                    final_path = os.path.join(self.download_dir, new_filename)
                                    counter += 1
                                print(f"📝 File already exists, saving as: {os.path.basename(final_path)}")
                            
                            try:
                                os.rename(filepath, final_path)
                                completed_files.append(final_path)
                                initial_files.add(filename)  # Mark as processed
                            except Exception as move_error:
                                print(f"⚠️ Error moving file: {str(move_error)}")
                                # Try copy and delete instead
                                try:
                                    import shutil
                                    shutil.copy2(filepath, final_path)
                                    os.remove(filepath)
                                    completed_files.append(final_path)
                                    initial_files.add(filename)
                                except Exception as copy_error:
                                    print(f"❌ Failed to copy file: {str(copy_error)}")
                        else:
                            print(f"⏳ Still downloading: {filename} ({current_size:,} bytes)")
                    except Exception as e:
                        print(f"⚠️ Error checking file {filename}: {str(e)}")
            
            # Check if any temporary files exist
            temp_files = [f for f in current_files if f.endswith(('.part', '.crdownload', '.tmp'))]
            
            if download_started and not temp_files and len(new_files) > 0:
                # No more temporary files and we have new complete files
                print("✅ All downloads appear to be complete")
                time.sleep(2)  # Final wait to ensure completion
                break
            
            time.sleep(2)
            
            # Provide periodic updates
            if int(time.time() - start_time) % 10 == 0:
                elapsed = int(time.time() - start_time)
                print(f"⏳ Waiting for downloads... {elapsed}/{timeout} seconds")
        
        # Final check for any remaining files in temp directory
        final_temp_files = set(self._get_download_files()) - initial_files
        for filename in final_temp_files:
            if not filename.endswith(('.part', '.crdownload', '.tmp')):
                filepath = os.path.join(self.temp_download_dir, filename)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    final_path = os.path.join(self.download_dir, filename)
                    if os.path.exists(final_path):
                        base_name, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(final_path):
                            new_filename = f"{base_name}_{counter}{ext}"
                            final_path = os.path.join(self.download_dir, new_filename)
                            counter += 1
                    try:
                        import shutil
                        shutil.move(filepath, final_path)
                        completed_files.append(final_path)
                        print(f"✅ Moved remaining file: {os.path.basename(final_path)}")
                    except:
                        pass
        
        if completed_files:
            print(f"✅ Successfully downloaded {len(completed_files)} file(s):")
            for filepath in completed_files:
                print(f"   📄 {os.path.basename(filepath)}")
            return True
        else:
            print("⚠️ No completed downloads detected")
            return False
    
    def handle_alert_if_present(self):
        """Handle JavaScript alerts if they appear"""
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            print(f"🚨 Alert detected: {alert_text}")
            alert.accept()
            print("✅ Alert accepted")
            time.sleep(1)
            return True
        except:
            return False
    
    def safe_click(self, element, use_js=False):
        """Safely click an element with alert handling"""
        try:
            if use_js:
                self.driver.execute_script("arguments[0].click();", element)
            else:
                element.click()
            
            # Check for alerts after click
            time.sleep(0.5)
            self.handle_alert_if_present()
            return True
            
        except UnexpectedAlertPresentException:
            print("🚨 Unexpected alert during click")
            self.handle_alert_if_present()
            return False
        except Exception as e:
            print(f"❌ Click failed: {str(e)}")
            return False
    
    def take_screenshot(self, filename_prefix):
        """Take screenshot for debugging"""
        try:
            filename = f"{filename_prefix}_{int(time.time())}.png"
            self.driver.save_screenshot(filename)
            print(f"📸 Screenshot saved to: {filename}")
        except Exception as e:
            print(f"⚠️ Could not take screenshot: {str(e)}")
    
    def wait_for_ajax_complete(self, timeout=30):
        """Wait for AJAX requests to complete"""
        print("⏳ Waiting for AJAX requests to complete...")
        
        def ajax_complete(driver):
            try:
                # Check if jQuery is loaded and if there are active requests
                jquery_active = driver.execute_script(
                    "return typeof jQuery !== 'undefined' && jQuery.active === 0"
                )
                
                # Check if RichFaces AJAX is complete (common in JSF applications)
                richfaces_complete = driver.execute_script(
                    "return typeof RichFaces === 'undefined' || "
                    "(typeof RichFaces.queue === 'undefined') || "
                    "(RichFaces.queue.getSize() === 0)"
                )
                
                # Check document ready state
                doc_ready = driver.execute_script("return document.readyState") == "complete"
                
                return jquery_active and richfaces_complete and doc_ready
                
            except Exception:
                return True  # If we can't check, assume it's complete
        
        try:
            WebDriverWait(self.driver, timeout).until(ajax_complete)
            print("✅ AJAX requests completed")
            return True
        except TimeoutException:
            print("⚠️ Timeout waiting for AJAX completion")
            return False
    
    def check_results_container_visibility(self):
        """Check if the results container is visible and has content"""
        try:
            # Look for the main results table
            results_table = self.driver.find_element(By.ID, "fPP:processosTable")
            is_displayed = results_table.is_displayed()
            
            # Check table content
            rows = results_table.find_elements(By.TAG_NAME, "tr")
            
            # Look for pagination elements
            pagination_selectors = [
                "//table[@id='fPP:processosTable']//td[contains(text(), 'resultados encontrados')]",
                "//table[@id='fPP:processosTable']//td[contains(text(), '««')]",
            ]
            
            pagination_found = False
            for selector in pagination_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements and any(elem.is_displayed() for elem in elements):
                        pagination_found = True
                        break
                except:
                    continue
            
            return is_displayed and len(rows) > 1 and pagination_found
            
        except Exception:
            return False
    
    def switch_to_new_tab(self):
        """Switch to the newly opened tab"""
        try:
            print("🔄 Checking for new tabs...")
            all_windows = self.driver.window_handles
            print(f"📊 Total windows/tabs: {len(all_windows)}")
            
            if len(all_windows) > 1:
                # Find the new tab (not the original one)
                for window in all_windows:
                    if window != self.original_window:
                        print(f"🎯 Switching to new tab: {window}")
                        self.driver.switch_to.window(window)
                        
                        # Wait for the new tab to load
                        time.sleep(3)
                        current_url = self.driver.current_url
                        print(f"🌐 New tab URL: {current_url}")
                        
                        # Check if we're on the process details page
                        if "Detalhe" in current_url or "idProcesso" in current_url:
                            print("✅ Successfully switched to process details tab")
                            return True
                        else:
                            print(f"⚠️ New tab URL doesn't look like process details: {current_url}")
                
            print("❌ No new tab found or failed to switch")
            return False
            
        except Exception as e:
            print(f"❌ Error switching to new tab: {str(e)}")
            return False
    
    def login(self, cpf_cnpj, password):
        """Login to PJE-TJES system"""
        try:
            login_url = "https://pje.tjes.jus.br/pje/login.seam"
            print(f"📍 Navigating to: {login_url}")
            self.driver.get(login_url)
            
            print("⏳ Waiting for page to load completely...")
            self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            time.sleep(5)
            
            # Check for iframes
            print("🔍 Checking for iframes...")
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                print("🔄 Switching to iframe...")
                self.driver.switch_to.frame(iframes[0])
                time.sleep(2)
            
            # Find and fill username field
            username_field = self._find_login_field("username")
            if not username_field:
                print("❌ Could not find username field")
                return False
                
            print("📝 Filling CPF/CNPJ field...")
            username_field.clear()
            username_field.send_keys(cpf_cnpj)
            
            # Find and fill password field
            password_field = self._find_login_field("password")
            if not password_field:
                print("❌ Could not find password field")
                return False
                
            print("📝 Filling password field...")
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit form
            if not self._submit_login_form(password_field):
                return False
                
            print("⏳ Waiting for login response...")
            time.sleep(8)
            
            # Switch back to main frame
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            
            current_url = self.driver.current_url
            print(f"🌐 Current URL: {current_url}")
            
            if "login" in current_url.lower():
                print("⚠️ Still on login page - login may have failed")
                return False
            else:
                print("✅ Login appears successful!")
                return True
                
        except Exception as e:
            print(f"❌ Error during login: {str(e)}")
            return False
    
    def _find_login_field(self, field_type):
        """Helper method to find login form fields"""
        if field_type == "username":
            selectors = [
                (By.ID, "username"),
                (By.NAME, "username"),
                (By.CSS_SELECTOR, "input[type='text']"),
            ]
        else:  # password
            selectors = [
                (By.ID, "password"),
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
            ]
        
        for selector_type, selector_value in selectors:
            try:
                elements = self.driver.find_elements(selector_type, selector_value)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        print(f"✅ Found {field_type} field")
                        return element
            except Exception:
                continue
        
        return None
    
    def _submit_login_form(self, password_field):
        """Helper method to submit login form"""
        submit_selectors = [
            (By.ID, "kc-login"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]
        
        for selector_type, selector_value in submit_selectors:
            try:
                elements = self.driver.find_elements(selector_type, selector_value)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        print("🔐 Clicking submit button...")
                        self.safe_click(element)
                        return True
            except Exception:
                continue
        
        # Fallback to Enter key
        password_field.send_keys(Keys.RETURN)
        return True
    
    def navigate_to_search_page(self):
        """Navigate to the process search page"""
        try:
            print("🧭 Navigating to search page...")
            
            search_url = "https://pje.tjes.jus.br/pje/Processo/ConsultaProcesso/listView.seam"
            print(f"📍 Attempting direct navigation to: {search_url}")
            self.driver.get(search_url)
            time.sleep(5)
            
            self.wait_for_ajax_complete()
            
            if "ConsultaProcesso" in self.driver.current_url:
                print("✅ Successfully navigated to search page")
                return True
            
            print("❌ Failed to navigate to search page")
            return False
            
        except Exception as e:
            print(f"❌ Error navigating to search page: {str(e)}")
            return False

    def search_process(self, process_number):
        """Search for a specific process and click on it"""
        try:
            print(f"🔍 Searching for process: {process_number}")
            
            # Take initial screenshot
            self.take_screenshot("01_before_search")
            
            # Check initial state of results container
            initial_visibility = self.check_results_container_visibility()
            print(f"📊 Initial results container visible: {initial_visibility}")
            
            # Find ALL process number fields and check their current state
            print("🔍 Checking all process number fields and their current values...")
            
            process_fields = [
                ("Sequential", "fPP:numeroProcesso:numeroSequencial", process_number[:7]),
                ("Check Digits", "fPP:numeroProcesso:digitoVerificador", process_number[7:9]),
                ("Year", "fPP:numeroProcesso:anoProcesso", process_number[9:13]),
                ("Segment", "fPP:numeroProcesso:segmentoTribunal", process_number[13:14]),
                ("Tribunal", "fPP:numeroProcesso:codigoTribunal", process_number[14:16]),
                ("Origin", "fPP:numeroProcesso:codigoOrigem", process_number[16:20])
            ]
            
            # First, check what's currently in each field
            for field_name, field_id, expected_value in process_fields:
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    current_value = field.get_attribute('value') or ''
                    placeholder = field.get_attribute('placeholder') or ''
                    readonly = field.get_attribute('readonly')
                    print(f"📝 {field_name} field: value='{current_value}', placeholder='{placeholder}', readonly={readonly}")
                except Exception as e:
                    print(f"❌ Could not find {field_name} field: {str(e)}")
            
            # Strategy: Fill each field individually with the correct portion
            print("\n🎯 Filling each field individually...")
            
            for field_name, field_id, expected_value in process_fields:
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    
                    # Skip if field is readonly
                    if field.get_attribute('readonly'):
                        print(f"⚠️ Skipping {field_name} - field is readonly")
                        continue
                    
                    # Clear and fill the field
                    field.clear()
                    time.sleep(0.2)
                    field.send_keys(expected_value)
                    time.sleep(0.2)
                    
                    # Verify the value was set
                    actual_value = field.get_attribute('value')
                    if actual_value == expected_value:
                        print(f"✅ {field_name}: '{actual_value}' ✓")
                    else:
                        print(f"⚠️ {field_name}: expected '{expected_value}', got '{actual_value}'")
                        
                except Exception as e:
                    print(f"❌ Error filling {field_name}: {str(e)}")
            
            # Take screenshot after filling fields
            self.take_screenshot("02_after_number_entry")
            
            # Final verification - show what's in all fields
            print("\n📋 Final field verification:")
            for field_name, field_id, expected_value in process_fields:
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    actual_value = field.get_attribute('value') or ''
                    status = "✅" if actual_value == expected_value else "❌"
                    print(f"{status} {field_name}: '{actual_value}' (expected: '{expected_value}')")
                except:
                    print(f"❌ {field_name}: field not found")
            
            # Find the search button
            search_button = self.driver.find_element(By.CSS_SELECTOR, "input[value='Pesquisar']")
            if not search_button:
                print("❌ Could not find search button")
                return False
            
            print("🎯 Clicking search button...")
            
            # Click the search button
            if not self.safe_click(search_button):
                # Try JavaScript click as fallback
                if not self.safe_click(search_button, use_js=True):
                    print("❌ Failed to click search button")
                    return False
            
            print("✅ Search button clicked")
            self.take_screenshot("03_immediately_after_click")
            
            # Wait for results
            time.sleep(3)
            self.wait_for_ajax_complete()
            time.sleep(2)
            
            self.take_screenshot("04_after_ajax_wait")
            
            # Check if results container is still visible
            final_visibility = self.check_results_container_visibility()
            print(f"📊 Results container visible after search: {final_visibility}")
            
            if not final_visibility:
                print("❌ Results container not visible after search")
                return False
            
            # Now look for the process link
            print("🔍 Looking for process link in results...")
            time.sleep(3)  # Wait a bit more for results to populate
            
            # Format the process number for display
            formatted_process = self._format_process_number(process_number)
            print(f"🔍 Looking for EXACT process number: {formatted_process}")
            
            # Look for exact match only
            process_link = None
            
            # Try to find all links in the results table
            try:
                result_links = self.driver.find_elements(By.XPATH, "//table[@id='fPP:processosTable']//a")
                print(f"🔍 Found {len(result_links)} links in results table")
                
                for link in result_links:
                    if link.is_displayed():
                        link_text = link.text.strip()
                        if link_text:  # Only process non-empty links
                            print(f"📋 Checking link: '{link_text}'")
                            
                            # Remove all non-numeric characters for comparison
                            link_numbers_only = re.sub(r'[^\d]', '', link_text)
                            
                            # Check for exact match
                            if link_numbers_only == process_number:
                                process_link = link
                                print(f"✅ EXACT MATCH FOUND: '{link_text}'")
                                break
                            elif formatted_process == link_text:
                                process_link = link
                                print(f"✅ EXACT MATCH FOUND (formatted): '{link_text}'")
                                break
                            else:
                                # Show why it didn't match
                                if len(link_numbers_only) >= 15:
                                    print(f"   ❌ Not a match - Expected: {process_number}, Got: {link_numbers_only}")
                
            except Exception as e:
                print(f"❌ Error searching for process links: {str(e)}")
            
            if not process_link:
                print("❌ EXACT process number not found in results!")
                print(f"❌ The process {formatted_process} was not found in the search results.")
                self.take_screenshot("05_process_not_found")
                return False
            
            # Store current number of windows before clicking
            windows_before = len(self.driver.window_handles)
            print(f"📊 Windows before clicking: {windows_before}")
            
            # Click the process link
            print("🎯 Clicking on process link...")
            self.take_screenshot("05_before_process_click")
            
            try:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", process_link)
                time.sleep(1)
                
                # Highlight the element
                self.driver.execute_script("arguments[0].style.border='3px solid red';", process_link)
                time.sleep(1)
                
                # Click the link
                if not self.safe_click(process_link):
                    print("❌ Failed to click process link")
                    return False
                    
                print("✅ Successfully clicked process link")
                
                # Wait for new tab to open
                print("⏳ Waiting for new tab to open...")
                time.sleep(5)
                
                # Check if new tab opened
                windows_after = len(self.driver.window_handles)
                print(f"📊 Windows after clicking: {windows_after}")
                
                if windows_after > windows_before:
                    print("🆕 New tab detected! Switching to new tab...")
                    if self.switch_to_new_tab():
                        print("🎉 Successfully navigated to process page!")
                        return True
                    else:
                        print("❌ Failed to switch to new tab")
                        return False
                else:
                    # Check if we're still on the same page but URL changed
                    current_url = self.driver.current_url
                    print(f"🌐 Current URL: {current_url}")
                    
                    if ("idProcesso" in current_url or 
                        "Detalhe" in current_url or
                        "ConsultaProcesso" not in current_url):
                        print("🎉 Successfully navigated to process page (same tab)!")
                        return True
                    else:
                        print("⚠️ Still on search page")
                        return False
                    
            except Exception as e:
                print(f"❌ Error clicking process link: {str(e)}")
                return False
            
        except Exception as e:
            print(f"❌ Error searching for process: {str(e)}")
            return False
    
    def _format_process_number(self, process_number):
        """Format process number with dots and dash"""
        if len(process_number) == 20:
            return f"{process_number[:7]}-{process_number[7:9]}.{process_number[9:13]}.{process_number[13]}.{process_number[14:16]}.{process_number[16:]}"
        return process_number
    
    def download_documents(self):
        """Download available documents from the process page using the modal system"""
        try:
            print("📄 Looking for download button on process page...")
            time.sleep(5)
            
            # Get initial files in download directory
            initial_files = set(self._get_download_files())
            
            self.take_screenshot("06_process_page_loaded")
            
            # Look for download button/icon in the toolbar
            download_selectors = [
                (By.XPATH, "//a[contains(@title, 'download') or contains(@title, 'Download')]"),
                (By.XPATH, "//img[contains(@alt, 'download') or contains(@alt, 'Download')]/parent::a"),
                (By.XPATH, "//span[contains(@class, 'download')]/parent::a"),
                (By.CSS_SELECTOR, "a[href*='download']"),
                (By.XPATH, "//a[contains(@onclick, 'download')]"),
                # Look for specific PJE download elements
                (By.XPATH, "//a[@title='Baixar autos do processo']"),
                (By.XPATH, "//img[@alt='Baixar autos do processo']/parent::a"),
                # Generic download icons in toolbar
                (By.XPATH, "//div[contains(@class, 'toolbar')]//a"),
                (By.XPATH, "//div[contains(@class, 'header')]//a[contains(@href, 'download') or contains(@onclick, 'download')]"),
                # Look in the right sidebar or action buttons
                (By.XPATH, "//a[contains(text(), 'Download') or contains(text(), 'download')]"),
                (By.XPATH, "//button[contains(text(), 'Download') or contains(text(), 'download')]"),
            ]
            
            download_button = None
            for selector_type, selector_value in download_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for element in elements:
                        if element.is_displayed():
                            element_title = element.get_attribute('title') or ''
                            element_text = element.text.strip()
                            element_onclick = element.get_attribute('onclick') or ''
                            
                            print(f"🔍 Found potential download element: text='{element_text}', title='{element_title}', onclick='{element_onclick[:50]}...'")
                            
                            if ('download' in element_title.lower() or
                                'download' in element_text.lower() or
                                'download' in element_onclick.lower() or
                                'baixar' in element_title.lower() or
                                'baixar' in element_text.lower()):
                                download_button = element
                                print(f"✅ Selected download button: '{element_text}' / '{element_title}'")
                                break
                    if download_button:
                        break
                except Exception as e:
                    print(f"⚠️ Error with selector {selector_value}: {str(e)}")
                    continue
            
            if not download_button:
                print("❌ Could not find download button")
                # Take a screenshot to help debug
                self.take_screenshot("07_no_download_button_found")
                
                # Try to find any clickable elements in the toolbar for debugging
                print("🔍 Debug: Looking for any toolbar elements...")
                try:
                    toolbar_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'toolbar')]//a | //div[contains(@class, 'header')]//a")
                    print(f"🔍 Found {len(toolbar_elements)} toolbar elements")
                    for i, elem in enumerate(toolbar_elements[:5]):  # Show first 5
                        try:
                            print(f"  Toolbar element {i+1}: '{elem.text}' / '{elem.get_attribute('title')}'")
                        except:
                            pass
                except:
                    pass
                
                return False
            
            # Click the download button to open the modal
            print("🎯 Clicking download button to open modal...")
            try:
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                time.sleep(1)
                
                # Highlight and click
                self.driver.execute_script("arguments[0].style.border='3px solid red';", download_button)
                time.sleep(1)
                
                if not self.safe_click(download_button):
                    # Try JavaScript click as fallback
                    if not self.safe_click(download_button, use_js=True):
                        print("❌ Failed to click download button")
                        return False
                
                print("✅ Download button clicked")
                
                # Wait for modal to appear with AJAX handling
                print("⏳ Waiting for modal to load...")
                time.sleep(2)
                self.wait_for_ajax_complete(timeout=15)
                time.sleep(3)
                self.take_screenshot("08_after_download_click")
                
            except Exception as e:
                print(f"❌ Error clicking download button: {str(e)}")
                return False
            
            # Look for the download modal with improved waiting
            print("🔍 Looking for download modal...")
            
            # Wait for modal to be visible with multiple attempts
            modal_selectors = [
                (By.XPATH, "//div[contains(@class, 'modal') and contains(@style, 'display: block')]"),
                (By.XPATH, "//div[contains(@id, 'modal') and contains(@style, 'display: block')]"),
                (By.XPATH, "//div[contains(text(), 'Tipo de documento')]"),
                (By.XPATH, "//select[contains(@id, 'tipo') or contains(@id, 'Tipo')]"),
                (By.XPATH, "//div[contains(text(), 'Tipo de documento')]/parent::div"),
                # Additional selectors for modal detection
                (By.XPATH, "//form[contains(@id, 'form')]//select"),
                (By.XPATH, "//div[contains(@style, 'display: block')]//select"),
                (By.XPATH, "//div[contains(@class, 'ui-dialog')]"),
                (By.XPATH, "//div[@role='dialog']"),
            ]
            
            modal_found = False
            modal_attempts = 0
            max_modal_attempts = 5
            
            while not modal_found and modal_attempts < max_modal_attempts:
                modal_attempts += 1
                print(f"🔍 Modal detection attempt {modal_attempts}/{max_modal_attempts}")
                
                # Check for any alerts first
                self.handle_alert_if_present()
                
                for selector_type, selector_value in modal_selectors:
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        for element in elements:
                            if element.is_displayed():
                                print(f"✅ Found modal element: {element.tag_name} with {selector_value}")
                                modal_found = True
                                break
                        if modal_found:
                            break
                    except Exception:
                        continue
                
                if not modal_found:
                    print(f"⏳ Modal not found in attempt {modal_attempts}, waiting...")
                    time.sleep(2)
                    self.wait_for_ajax_complete(timeout=10)
            
            if modal_found:
                print("✅ Download modal is visible")
                self.take_screenshot("09_modal_visible")
                
                # Give modal content more time to fully load
                print("⏳ Waiting for modal content to fully load...")
                time.sleep(3)
                self.wait_for_ajax_complete(timeout=10)
                time.sleep(2)
                
                # Look for the DOWNLOAD button in the modal
                print("🔍 Looking for DOWNLOAD button in modal...")
                
                download_modal_button_selectors = [
                    # Exact text matches
                    (By.XPATH, "//button[text()='DOWNLOAD']"),
                    (By.XPATH, "//input[@value='DOWNLOAD']"),
                    (By.XPATH, "//a[text()='DOWNLOAD']"),
                    
                    # Case insensitive text matches
                    (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]"),
                    (By.XPATH, "//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]"),
                    
                    # Portuguese variations
                    (By.XPATH, "//button[contains(text(), 'Baixar')]"),
                    (By.XPATH, "//input[@value='Baixar']"),
                    (By.XPATH, "//button[contains(text(), 'Download')]"),
                    (By.XPATH, "//input[contains(@value, 'Download')]"),
                    
                    # Class-based searches
                    (By.XPATH, "//button[contains(@class, 'download')]"),
                    (By.XPATH, "//input[contains(@class, 'download')]"),
                    (By.XPATH, "//a[contains(@class, 'download')]"),
                    
                    # Color-based (blue buttons as seen in screenshots)
                    (By.XPATH, "//button[contains(@class, 'blue')]"),
                    (By.XPATH, "//input[contains(@class, 'blue')]"),
                    (By.XPATH, "//a[contains(@class, 'blue')]"),
                    (By.XPATH, "//button[contains(@style, 'blue')]"),
                    
                    # Generic button searches in modal context
                    (By.XPATH, "//div[contains(@class, 'modal')]//button"),
                    (By.XPATH, "//div[contains(@class, 'modal')]//input[@type='button']"),
                    (By.XPATH, "//div[contains(@class, 'modal')]//input[@type='submit']"),
                    (By.XPATH, "//form//button[position()=1]"),  # First button in form
                    (By.XPATH, "//form//input[@type='submit']"),
                    
                    # ID-based searches
                    (By.XPATH, "//button[contains(@id, 'download')]"),
                    (By.XPATH, "//input[contains(@id, 'download')]"),
                    (By.XPATH, "//button[contains(@id, 'baixar')]"),
                    
                    # onclick-based searches
                    (By.XPATH, "//button[contains(@onclick, 'download')]"),
                    (By.XPATH, "//input[contains(@onclick, 'download')]"),
                    (By.XPATH, "//a[contains(@onclick, 'download')]"),
                ]
                
                modal_download_button = None
                for selector_type, selector_value in download_modal_button_selectors:
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        for element in elements:
                            if element.is_displayed():
                                button_text = element.text.strip()
                                button_value = element.get_attribute('value') or ''
                                button_class = element.get_attribute('class') or ''
                                combined_text = f"{button_text} {button_value}".strip()
                                
                                print(f"🔍 Found potential modal button: text='{button_text}' value='{button_value}' class='{button_class[:30]}...'")
                                
                                # More flexible matching
                                if (any(keyword in combined_text.upper() for keyword in ['DOWNLOAD', 'BAIXAR']) or
                                    'download' in button_class.lower() or
                                    'blue' in button_class.lower()):
                                    modal_download_button = element
                                    print(f"✅ Selected modal download button: '{combined_text}' / class: '{button_class}'")
                                    break
                        if modal_download_button:
                            break
                    except Exception as e:
                        print(f"⚠️ Error with selector {selector_value}: {str(e)}")
                        continue
                
                if not modal_download_button:
                    print("❌ Could not find any download button in modal")
                    self.take_screenshot("10_no_modal_download_button")
                    return False
                
                # Click the DOWNLOAD button in modal
                print("🎯 Clicking DOWNLOAD button in modal...")
                if not self.safe_click(modal_download_button):
                    if not self.safe_click(modal_download_button, use_js=True):
                        print("❌ Failed to click modal download button")
                        return False
                
                print("✅ Modal DOWNLOAD button clicked")
                time.sleep(3)
                
                self.take_screenshot("11_after_modal_download_click")
                
                # Look for confirmation dialog
                print("🔍 Looking for confirmation dialog...")
                time.sleep(2)
                
                # Check for alerts
                self.handle_alert_if_present()
                
                confirmation_selectors = [
                    (By.XPATH, "//div[contains(text(), 'Confirma o download')]"),
                    (By.XPATH, "//div[contains(text(), 'confirmação')]"),
                    (By.XPATH, "//div[contains(@class, 'confirm')]"),
                    (By.XPATH, "//div[contains(@class, 'dialog')]"),
                    # Look for the specific text from the screenshot
                    (By.XPATH, "//div[contains(text(), 'pode demorar alguns minutos')]"),
                    (By.XPATH, "//button[text()='OK']"),
                    (By.XPATH, "//input[@value='OK']"),
                    (By.XPATH, "//button[text()='Sim']"),
                    (By.XPATH, "//button[text()='Confirmar']"),
                    (By.XPATH, "//button[contains(@class, 'confirm')]"),
                ]
                
                confirmation_dialog = False
                ok_button = None
                
                for selector_type, selector_value in confirmation_selectors:
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        for element in elements:
                            if element.is_displayed():
                                element_text = element.text.strip()
                                print(f"🔍 Found confirmation element: '{element_text}'")
                                
                                if (element.tag_name.lower() in ['button', 'input'] and 
                                    any(confirm_text in element_text.upper() for confirm_text in ['OK', 'SIM', 'CONFIRMAR']) or 
                                    element.get_attribute('value') in ['OK', 'Sim', 'Confirmar']):
                                    ok_button = element
                                    confirmation_dialog = True
                                    print(f"✅ Found confirmation button: '{element_text}'")
                                elif ('confirma' in element_text.lower() or 
                                      'download' in element_text.lower() or
                                      'minutos' in element_text.lower()):
                                    confirmation_dialog = True
                                    print("✅ Confirmation dialog detected")
                    except Exception:
                        continue
                
                if confirmation_dialog and ok_button:
                    print("🎯 Clicking confirmation button...")
                    if not self.safe_click(ok_button):
                        if not self.safe_click(ok_button, use_js=True):
                            print("❌ Failed to click OK button")
                            return False
                    
                    print("✅ Confirmation button clicked")
                    time.sleep(3)
                    self.take_screenshot("12_after_confirmation")
                
                # Wait for download to start and complete
                print("⏳ Monitoring download progress...")
                download_success = self._wait_for_download_complete(timeout=120, initial_files=initial_files)
                
                if download_success:
                    print("✅ Documents downloaded successfully!")
                    self.take_screenshot("13_download_completed")
                    return True
                else:
                    print("⚠️ Download monitoring timed out or no files detected")
                    self.take_screenshot("13_download_timeout")
                    
                    # Check if files might have been downloaded anyway
                    final_files = set(self._get_download_files())
                    new_files = final_files - initial_files
                    if new_files:
                        print(f"✅ Found {len(new_files)} new file(s) despite timeout")
                        return True
                    
                    return False
                    
            else:
                print("❌ Download modal not found")
                self.take_screenshot("09_no_modal_found")
                
                # Fallback: try direct document links
                print("🔄 Fallback: Looking for direct document links...")
                return self._download_direct_links(initial_files)
                
        except Exception as e:
            print(f"❌ Error in document download: {str(e)}")
            self.take_screenshot("error_download")
            return False
    
    def _download_direct_links(self, initial_files=None):
        """Fallback method to look for direct document download links"""
        try:
            print("📄 Looking for direct document download links...")
            
            if initial_files is None:
                initial_files = set(self._get_download_files())
            
            # Look for document links using various strategies
            document_selectors = [
                (By.XPATH, "//a[contains(@href, 'download') or contains(@onclick, 'download')]"),
                (By.XPATH, "//a[contains(text(), 'PDF') or contains(text(), 'pdf')]"),
                (By.CSS_SELECTOR, "a[href*='documento']"),
                (By.XPATH, "//a[contains(@href, 'visualizar')]"),
                (By.XPATH, "//img[@alt='Visualizar documento']/parent::a"),
                (By.XPATH, "//a[contains(@title, 'documento')]"),
                # Look for links in document lists or tables
                (By.XPATH, "//table//a[contains(@href, 'doc') or contains(@href, 'pdf')]"),
                (By.XPATH, "//ul//a[contains(@href, 'doc') or contains(@href, 'pdf')]"),
                (By.XPATH, "//div[contains(@class, 'document')]//a"),
            ]
            
            documents_found = []
            for selector_type, selector_value in document_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for element in elements:
                        if element.is_displayed():
                            link_text = element.text.strip()
                            link_href = element.get_attribute('href') or ''
                            link_title = element.get_attribute('title') or ''
                            
                            if ('download' in link_href.lower() or
                                'documento' in link_href.lower() or
                                'visualizar' in link_href.lower() or
                                'pdf' in link_text.lower() or
                                'doc' in link_href.lower()):
                                
                                print(f"🔍 Found document link: '{link_text}' -> {link_href[:50]}...")
                                documents_found.append(element)
                except Exception:
                    continue
            
            if not documents_found:
                print("❌ No direct document links found")
                return False
            
            print(f"📄 Found {len(documents_found)} document link(s)")
            
            # Download each document
            for i, doc in enumerate(documents_found[:5]):  # Limit to first 5 to avoid overload
                try:
                    print(f"📥 Downloading document {i+1}...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", doc)
                    time.sleep(1)
                    
                    # Highlight the link
                    self.driver.execute_script("arguments[0].style.border='3px solid green';", doc)
                    time.sleep(1)
                    
                    if not self.safe_click(doc):
                        if not self.safe_click(doc, use_js=True):
                            print(f"❌ Failed to click document {i+1}")
                            continue
                    
                    time.sleep(3)
                    print(f"✅ Document {i+1} click successful")
                    
                    # Check for alerts
                    self.handle_alert_if_present()
                    
                except Exception as e:
                    print(f"❌ Error downloading document {i+1}: {str(e)}")
            
            # Wait for downloads to complete
            print("⏳ Waiting for direct downloads to complete...")
            time.sleep(10)
            
            # Check if any new files were downloaded
            final_files = set(self._get_download_files())
            new_files = final_files - initial_files
            
            if new_files:
                print(f"✅ Downloaded {len(new_files)} file(s) via direct links")
                for filename in new_files:
                    print(f"   📄 {filename}")
                return True
            else:
                print("❌ No files were downloaded via direct links")
                return False
            
        except Exception as e:
            print(f"❌ Error in direct link download: {str(e)}")
            return False
    
    def run_automation(self, cpf_cnpj, password, process_number):
        """Run the complete automation process for a single process"""
        try:
            # Note: Driver setup and login should be done outside this method for batch processing
            
            # Navigate to search page
            if not self.navigate_to_search_page():
                print("❌ Failed to navigate to search page")
                return False
            
            # Search for process and click on it
            if not self.search_process(process_number):
                print("❌ Failed to find and click process")
                return False
            
            # Download documents using modal system
            if not self.download_documents():
                print("❌ Failed to download documents")
                return False
            
            print("✅ Process automation completed successfully!")
            
            # List only the downloaded files from this session
            try:
                # Get list of files that start with the process number
                process_prefix = process_number[:7]  # Use first 7 digits as prefix
                session_files = []
                
                for file in os.listdir(self.download_dir):
                    filepath = os.path.join(self.download_dir, file)
                    if os.path.isfile(filepath):
                        # Check if file was created recently (within last 5 minutes)
                        file_mod_time = os.path.getmtime(filepath)
                        current_time = time.time()
                        if (current_time - file_mod_time) < 300:  # 5 minutes
                            session_files.append((file, os.path.getsize(filepath)))
                
                if session_files:
                    print(f"\n📄 Files downloaded for this process:")
                    for filename, size in session_files:
                        print(f"   - {filename} ({size:,} bytes)")
                else:
                    print("\n⚠️ No new files detected in download folder")
                    
            except Exception as e:
                print(f"⚠️ Could not list downloaded files: {str(e)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in automation: {str(e)}")
            return False

def main():
    """Main function"""
    print("🤖 PJE-TJES Automation Robot - Optimized Version")
    print("=" * 80)
    
    # Configuration
    USE_HARDCODED_CREDENTIALS = True  # Set to True to use hardcoded credentials
    
    # Hardcoded credentials (only used if USE_HARDCODED_CREDENTIALS is True)
    HARDCODED_CPF = "03484547758"
    HARDCODED_PASSWORD = "150406C@rlos"
    
    # Get credentials
    if USE_HARDCODED_CREDENTIALS:
        print("🔐 Using hardcoded credentials")
        cpf_cnpj = HARDCODED_CPF
        password = HARDCODED_PASSWORD
    else:
        # Get user input
        cpf_cnpj = input("Digite o CPF/CNPJ: ").strip()
        password = input("Digite a senha: ").strip()
    
    if not cpf_cnpj or not password:
        print("❌ Por favor, preencha as credenciais")
        return
    
    # Get process numbers
    print("\n📋 Digite os números dos processos (um por linha)")
    print("Pressione Enter duas vezes quando terminar:")
    
    process_numbers = []
    while True:
        process_input = input().strip()
        if process_input == "":
            if process_numbers:  # If we have at least one process, break
                break
            else:
                print("⚠️ Digite pelo menos um número de processo")
                continue
        
        # Clean process number (remove any formatting)
        process_number = re.sub(r'[^\d]', '', process_input)
        
        # Validate length
        if len(process_number) != 20:
            print(f"⚠️ Número do processo deve ter 20 dígitos, encontrado {len(process_number)}")
            continue_anyway = input("Adicionar mesmo assim? (s/n): ").strip().lower()
            if continue_anyway != 's':
                continue
        
        process_numbers.append(process_number)
        # Show formatted version
        formatted = process_number[:7] + "-" + process_number[7:9] + "." + process_number[9:13] + "." + process_number[13] + "." + process_number[14:16] + "." + process_number[16:] if len(process_number) == 20 else process_number
        print(f"✅ Adicionado: {formatted}")
    
    if not process_numbers:
        print("❌ Nenhum processo foi adicionado")
        return
    
    print(f"\n📊 Total de processos para buscar: {len(process_numbers)}")
    
    # Create automation instance
    automation = PJEAutomationOptimized(headless=False)
    
    # Results tracking
    successful_downloads = []
    failed_downloads = []
    
    try:
        # Setup driver once
        automation.setup_driver()
        
        # Login once
        print("\n" + "="*50)
        print("STEP 1: LOGIN")
        print("="*50)
        if not automation.login(cpf_cnpj, password):
            print("❌ Login failed")
            return
        
        # Process each process number
        for idx, process_number in enumerate(process_numbers, 1):
            print("\n" + "="*80)
            print(f"🔄 PROCESSANDO {idx}/{len(process_numbers)}")
            print("="*80)
            
            formatted = process_number[:7] + "-" + process_number[7:9] + "." + process_number[9:13] + "." + process_number[13] + "." + process_number[14:16] + "." + process_number[16:] if len(process_number) == 20 else process_number
            print(f"📋 Processo: {formatted}")
            
            try:
                # Navigate to search page
                print("\n" + "="*50)
                print("STEP 2: NAVIGATE TO SEARCH PAGE")
                print("="*50)
                if not automation.navigate_to_search_page():
                    print("❌ Failed to navigate to search page")
                    failed_downloads.append((process_number, "Failed to navigate to search page"))
                    continue
                
                # Search for process
                print("\n" + "="*50)
                print("STEP 3: SEARCH FOR PROCESS")
                print("="*50)
                if not automation.search_process(process_number):
                    print("❌ Failed to find process")
                    failed_downloads.append((process_number, "Process not found"))
                    continue
                
                # Download documents
                print("\n" + "="*50)
                print("STEP 4: DOWNLOAD DOCUMENTS")
                print("="*50)
                if not automation.download_documents():
                    print("❌ Failed to download documents")
                    failed_downloads.append((process_number, "Download failed"))
                    continue
                
                successful_downloads.append(process_number)
                print(f"✅ Processo {formatted} concluído com sucesso!")
                
                # Close extra tabs if any
                if len(automation.driver.window_handles) > 1:
                    # Close all tabs except the original
                    for handle in automation.driver.window_handles:
                        if handle != automation.original_window:
                            automation.driver.switch_to.window(handle)
                            automation.driver.close()
                    automation.driver.switch_to.window(automation.original_window)
                
            except Exception as e:
                print(f"❌ Erro ao processar: {str(e)}")
                failed_downloads.append((process_number, str(e)))
                
                # Try to recover
                try:
                    # Close all tabs and go back to original
                    for handle in automation.driver.window_handles:
                        if handle != automation.original_window:
                            automation.driver.switch_to.window(handle)
                            automation.driver.close()
                    automation.driver.switch_to.window(automation.original_window)
                except:
                    pass
            
            # Small delay between processes
            if idx < len(process_numbers):
                print("\n⏳ Aguardando 3 segundos antes do próximo processo...")
                time.sleep(3)
        
        # Final report
        print("\n" + "="*80)
        print("📊 RELATÓRIO FINAL")
        print("="*80)
        
        print(f"\n✅ Downloads bem-sucedidos: {len(successful_downloads)}")
        for process in successful_downloads:
            formatted = process[:7] + "-" + process[7:9] + "." + process[9:13] + "." + process[13] + "." + process[14:16] + "." + process[16:] if len(process) == 20 else process
            print(f"   - {formatted}")
        
        if failed_downloads:
            print(f"\n❌ Downloads falhados: {len(failed_downloads)}")
            for process, reason in failed_downloads:
                formatted = process[:7] + "-" + process[7:9] + "." + process[9:13] + "." + process[13] + "." + process[14:16] + "." + process[16:] if len(process) == 20 else process
                print(f"   - {formatted}: {reason}")
        
        print(f"\n📁 Arquivos salvos em: {automation.download_dir}")
        
    except Exception as e:
        print(f"\n❌ Erro crítico: {str(e)}")
    
    finally:
        if automation.driver:
            print("\n🔍 Mantendo navegador aberto por 15 segundos para verificação final...")
            try:
                automation.take_screenshot("final_state")
                time.sleep(15)
            except:
                pass
            print("🔚 Fechando navegador...")
            try:
                automation.driver.quit()
            except:
                pass
    
    input("\nPressione Enter para sair...")

if __name__ == "__main__":
    main()
