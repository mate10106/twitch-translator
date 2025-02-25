import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import speech_recognition as sr
from googletrans import Translator, LANGUAGES
from langdetect import detect
import pyaudio
import wave
import time
import numpy as np

class AudioTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Translator")
        
        # Translation variables
        self.target_lang = "en"
        self.translator = Translator()
        self.audio_queue = queue.Queue()
        
        # Debug mode
        self.debug_mode = True
        
        # GUI Setup
        self.create_control_window()
        self.create_overlay_window()
        
        # Audio Setup
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 100  # Make it very sensitive
        self.recognizer.dynamic_energy_threshold = True
        self.is_recording = False
        self.audio_thread = None
        
        # Add status message
        self.status_text = tk.StringVar()
        self.status_text.set("Ready")
        self.status_label = ttk.Label(self.control_win, textvariable=self.status_text)
        self.status_label.pack(pady=5)

    def create_control_window(self):
        self.control_win = tk.Toplevel(self.root)
        self.control_win.title("Settings")
        self.control_win.geometry("400x500")
        
        # Audio Device Selection
        ttk.Label(self.control_win, text="Audio Input Device:").pack(pady=5)
        self.audio_devices = self.get_audio_devices()
        self.device_combo = ttk.Combobox(self.control_win, values=list(self.audio_devices.keys()))
        if self.audio_devices:
            self.device_combo.set(list(self.audio_devices.keys())[0])
        self.device_combo.pack(pady=5)
        
        # Target Language Selection
        ttk.Label(self.control_win, text="Target Language (translate TO):").pack(pady=5)
        language_dict = {v: k for k, v in LANGUAGES.items()}
        self.lang_combo = ttk.Combobox(self.control_win, values=list(language_dict.keys()))
        self.lang_combo.set("english")
        self.lang_combo.pack(pady=5)
        
        # Source language indication
        ttk.Label(self.control_win, text="Detected Source:").pack(pady=5)
        self.source_label = ttk.Label(self.control_win, text="Not detected")
        self.source_label.pack(pady=5)
        
        # Audio sensitivity
        ttk.Label(self.control_win, text="Speech Detection Sensitivity:").pack(pady=5)
        self.sensitivity_slider = ttk.Scale(self.control_win, from_=50, to=500, orient="horizontal")
        self.sensitivity_slider.set(100)
        self.sensitivity_slider.pack(pady=5)
        
        # Test audio button
        ttk.Button(self.control_win, text="Test Audio Input", command=self.test_audio).pack(pady=5)
        
        # Debug output
        ttk.Label(self.control_win, text="Debug Log:").pack(pady=5)
        self.debug_text = tk.Text(self.control_win, height=10, width=45)
        self.debug_text.pack(pady=5)
        
        # Control buttons
        self.start_btn = ttk.Button(self.control_win, text="Start", command=self.toggle_recording)
        self.start_btn.pack(pady=10)
        
        # Opacity slider
        ttk.Label(self.control_win, text="Overlay Opacity:").pack(pady=5)
        self.opacity_slider = ttk.Scale(self.control_win, from_=0.1, to=1.0, orient="horizontal")
        self.opacity_slider.set(0.8)
        self.opacity_slider.pack(pady=5)
        self.opacity_slider.bind("<ButtonRelease-1>", self.update_opacity)

    def test_audio(self):
        """Test audio input for 5 seconds and show volume levels"""
        if self.is_recording:
            messagebox.showinfo("Recording in Progress", "Please stop recording first")
            return
            
        device_index = None
        if self.device_combo.get() in self.audio_devices:
            device_index = self.audio_devices[self.device_combo.get()]
        
        self.log_debug("Testing audio input for 5 seconds...")
        self.status_text.set("Testing audio...")
        
        p = pyaudio.PyAudio()
        try:
            chunk = 1024
            stream = p.open(format=pyaudio.paInt16,
                          channels=1,
                          rate=16000,
                          input=True,
                          input_device_index=device_index,
                          frames_per_buffer=chunk)
            
            # Test for 5 seconds
            for i in range(50):  # ~5 seconds
                data = stream.read(chunk, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                self.log_debug(f"Audio level: {volume:.1f}")
                self.root.update()
                time.sleep(0.1)
                
            if volume < 100:
                self.log_debug("WARNING: Audio levels very low! Check your audio source.")
                messagebox.showwarning("Low Audio", "Audio levels are very low. Please check your audio source.")
            else:
                self.log_debug(f"Audio test complete. Average level: {volume:.1f}")
                messagebox.showinfo("Audio Test", f"Audio test successful. Average level: {volume:.1f}")
                
        except Exception as e:
            self.log_debug(f"Audio test error: {e}")
            messagebox.showerror("Audio Test Error", str(e))
        finally:
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            p.terminate()
            self.status_text.set("Ready")

    def get_audio_devices(self):
        """Get a list of available audio input devices"""
        devices = {}
        p = pyaudio.PyAudio()
        
        try:
            info = p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            
            for i in range(num_devices):
                device_info = p.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels') > 0:
                    devices[f"{device_info.get('name')}"] = i
        except Exception as e:
            self.log_debug(f"Error getting devices: {e}")
        finally:
            p.terminate()
            
        return devices

    def log_debug(self, message):
        """Add a debug message to the debug text area"""
        if self.debug_mode:
            timestamp = time.strftime("%H:%M:%S")
            self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.debug_text.see(tk.END)
            print(message)  # Also print to console

    def update_opacity(self, event=None):
        opacity = self.opacity_slider.get()
        self.overlay.attributes("-alpha", opacity)

    def create_overlay_window(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.8)
        self.overlay.geometry("500x120+100+100")
        self.overlay.config(bg="black")
        
        self.subtitle_label = tk.Label(
            self.overlay,
            text="Translation will appear here",
            fg="white",
            bg="black",
            font=("Arial", 14),
            wraplength=480
        )
        self.subtitle_label.pack(expand=True, fill="both")
        
        # Drag functionality
        self.overlay.bind("<ButtonPress-1>", self.start_drag)
        self.overlay.bind("<B1-Motion>", self.on_drag)

    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def on_drag(self, event):
        x = self.overlay.winfo_x() - self._drag_start_x + event.x
        y = self.overlay.winfo_y() - self._drag_start_y + event.y
        self.overlay.geometry(f"+{x}+{y}")

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.start_btn.config(text="Stop")
            
            # Update target language from dropdown
            language_dict = {v: k for k, v in LANGUAGES.items()}
            selected_lang_name = self.lang_combo.get()
            if selected_lang_name in language_dict:
                self.target_lang = language_dict[selected_lang_name]
                self.log_debug(f"Set target language to: {self.target_lang}")
            
            # Set sensitivity from slider
            sensitivity = self.sensitivity_slider.get()
            self.recognizer.energy_threshold = sensitivity
            self.log_debug(f"Speech detection sensitivity set to: {sensitivity}")
            
            self.audio_thread = threading.Thread(target=self.record_audio)
            self.audio_thread.daemon = True
            self.audio_thread.start()
            self.process_audio()
            self.status_text.set("Recording started")
        else:
            self.is_recording = False
            self.start_btn.config(text="Start")
            self.status_text.set("Recording stopped")

    def record_audio(self):
        chunk = 1024
        sample_format = pyaudio.paInt16
        channels = 1
        rate = 16000  # Better for speech recognition
        
        p = pyaudio.PyAudio()
        
        # Get selected device index
        device_index = None
        if self.device_combo.get() in self.audio_devices:
            device_index = self.audio_devices[self.device_combo.get()]
            self.log_debug(f"Using audio device: {self.device_combo.get()} (index: {device_index})")
        
        try:
            stream = p.open(format=sample_format,
                          channels=channels,
                          rate=rate,
                          input=True,
                          input_device_index=device_index,
                          frames_per_buffer=chunk)
            
            self.subtitle_label.config(text="Listening...")
            self.log_debug("Audio stream opened, listening for speech")
            
            while self.is_recording:
                frames = []
                for _ in range(0, int(rate / chunk * 5)):  # 5 seconds of audio
                    try:
                        data = stream.read(chunk, exception_on_overflow=False)
                        frames.append(data)
                    except Exception as e:
                        self.log_debug(f"Error reading audio: {e}")
                
                # Only process if we have enough audio data
                if len(frames) > 0:
                    self.log_debug(f"Captured {len(frames)} audio frames")
                    self.audio_queue.put((frames, rate))
                else:
                    self.log_debug("No audio frames captured")
                    
        except Exception as e:
            self.log_debug(f"Stream creation error: {e}")
            messagebox.showerror("Audio Error", f"Could not open audio stream: {e}")
            self.is_recording = False
            self.start_btn.config(text="Start")
            
        finally:
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            p.terminate()
            self.log_debug("Audio recording stopped")

    def process_audio(self):
        try:
            if not self.audio_queue.empty():
                # Get audio frames from queue
                frames, rate = self.audio_queue.get_nowait()
                
                # Check audio levels
                audio_bytes = b''.join(frames)
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                volume = np.abs(audio_np).mean()
                self.log_debug(f"Audio volume level: {volume:.1f}")
                
                if volume < 50:
                    self.log_debug("WARNING: Audio volume very low!")
                
                # Create AudioData object
                audio_data = sr.AudioData(
                    audio_bytes,
                    sample_rate=rate,
                    sample_width=2
                )
                
                # Perform speech recognition
                try:
                    self.log_debug("Recognizing speech...")
                    text = self.recognizer.recognize_google(audio_data)
                    self.log_debug(f"Recognized text: {text}")
                    
                    if text:
                        try:
                            src_lang = detect(text)
                            self.log_debug(f"Detected language: {src_lang}")
                            self.source_label.config(text=f"Detected: {LANGUAGES.get(src_lang, src_lang)}")
                            
                            self.log_debug(f"Translating from {src_lang} to {self.target_lang}")
                            translated = self.translator.translate(
                                text, 
                                src=src_lang,
                                dest=self.target_lang
                            ).text
                            
                            # Update the subtitle text
                            self.subtitle_label.config(text=translated)
                            self.log_debug(f"Translation: {translated}")
                        except Exception as e:
                            self.log_debug(f"Translation error: {e}")
                            self.subtitle_label.config(text=f"Translation error: {str(e)[:50]}...")
                except sr.UnknownValueError:
                    self.log_debug("No speech detected in audio")
                except sr.RequestError as e:
                    self.log_debug(f"Recognition service error: {e}")
                    self.subtitle_label.config(text="Recognition service unavailable")
        
        except queue.Empty:
            # No audio data available, skip processing
            pass
        except Exception as e:
            self.log_debug(f"Process audio error: {e}")
        finally:
            # Continue processing loop if recording
            if self.is_recording:
                self.root.after(100, self.process_audio)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = AudioTranslatorApp(root)
    app.run()