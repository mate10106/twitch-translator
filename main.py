import tkinter as tk
from tkinter import ttk
import threading
import queue
import speech_recognition as sr
from googletrans import Translator, LANGUAGES
from langdetect import detect
import pyaudio
import wave
import time

class AudioTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Translator")
        
        # Translation variables
        self.target_lang = "en"
        self.translator = Translator()
        self.audio_queue = queue.Queue()
        
        # GUI Setup
        self.create_control_window()
        self.create_overlay_window()
        
        # Audio Setup
        self.recognizer = sr.Recognizer()
        self.is_recording = False
        self.audio_thread = None

    def create_control_window(self):
        self.control_win = tk.Toplevel(self.root)
        self.control_win.title("Settings")
        
        ttk.Label(self.control_win, text="Target Language:").pack(pady=5)
        self.lang_combo = ttk.Combobox(self.control_win, values=list(LANGUAGES.values()))
        self.lang_combo.set("english")
        self.lang_combo.pack(pady=5)
        
        self.start_btn = ttk.Button(self.control_win, text="Start", command=self.toggle_recording)
        self.start_btn.pack(pady=10)

    def create_overlay_window(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.geometry("400x100+100+100")
        self.overlay.config(bg="black")
        
        self.subtitle_label = tk.Label(
            self.overlay,
            text="",
            fg="white",
            bg="black",
            font=("Arial", 14),
            wraplength=380
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
            self.audio_thread = threading.Thread(target=self.record_audio)
            self.audio_thread.start()
            self.process_audio()
        else:
            self.is_recording = False
            self.start_btn.config(text="Start")

    def record_audio(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=44100,
                        input=True,
                        frames_per_buffer=1024)
        
        while self.is_recording:
            frames = []
            for _ in range(0, int(44100 / 1024 * 2)):  # 2 seconds
                data = stream.read(1024)
                frames.append(data)
            
            self.audio_queue.put(frames)
        
        stream.stop_stream()
        stream.close()
        p.terminate()

    def process_audio(self):
        try:
            if not self.audio_queue.empty():
            # Get audio frames from queue
                frames = self.audio_queue.get_nowait()
            
            # Create AudioData object
            audio_data = sr.AudioData(
                b''.join(frames),
                sample_rate=44100,
                sample_width=2
            )
            
            # Perform speech recognition
            try:
                text = self.recognizer.recognize_google(audio_data)
                src_lang = detect(text)
                translated = self.translator.translate(
                    text, 
                    dest=self.target_lang
                ).text
                self.subtitle_label.config(text=translated)
            except sr.UnknownValueError:
                print("Could not understand audio")
            except sr.RequestError as e:
                print(f"Recognition error: {e}")
    
        except queue.Empty:
        # No audio data available, skip processing
            pass
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