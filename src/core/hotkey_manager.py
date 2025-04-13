import threading
from pynput import keyboard
from PySide6.QtCore import QObject, Signal, QThread # Import QThread
import time # Import time for sleep
import platform

# --- Conditional Import for Windows Simulation ---
IS_WINDOWS = platform.system() == "Windows"
ctypes = None
if IS_WINDOWS:
    try:
        import ctypes
        # Define necessary structures and constants for SendInput
        # Pulled from various sources, common definitions
        PUL = ctypes.POINTER(ctypes.c_ulong)
        class KeyBdInput(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort),
                        ("wScan", ctypes.c_ushort),
                        ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong),
                        ("dwExtraInfo", PUL)]

        class HardwareInput(ctypes.Structure):
            _fields_ = [("uMsg", ctypes.c_ulong),
                        ("wParamL", ctypes.c_short),
                        ("wParamH", ctypes.c_ushort)]

        class MouseInput(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_long),
                        ("dy", ctypes.c_long),
                        ("mouseData", ctypes.c_ulong),
                        ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong),
                        ("dwExtraInfo", PUL)]

        class Input_I(ctypes.Union):
            _fields_ = [("ki", KeyBdInput),
                        ("mi", MouseInput),
                        ("hi", HardwareInput)]

        class Input(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong),
                        ("ii", Input_I)]

        # Constants for SendInput
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11  # Ctrl key
        VK_C = 0x43       # C key (virtual key code for 'C' key on standard layouts)

        print("[Hotkey Worker] Successfully imported ctypes and defined SendInput structures.")
    except ImportError:
        print("[Hotkey Worker] Warning: ctypes failed to import. Copy simulation on Windows unavailable.")
        IS_WINDOWS = False # Treat as non-windows if import fails
    except Exception as e:
        print(f"[Hotkey Worker] Error defining ctypes structures for SendInput: {e}")
        IS_WINDOWS = False # Assume failure if structures can't be defined
# --- End Conditional Import ---

class HotkeyListenerWorker(QObject):
    """Worker to run pynput listener in a separate thread."""
    # Signals for each hotkey, add more as needed
    toggle_engine_triggered = Signal()
    show_hide_triggered = Signal()
    next_profile_triggered = Signal()
    prev_profile_triggered = Signal()
    quick_add_rule_triggered = Signal()
    # Signal to report errors during listener setup or execution
    error_occurred = Signal(str)

    def __init__(self, hotkey_map):
        super().__init__()
        self.hotkey_map = hotkey_map # {pynput_combo_str: signal_name_str}
        self.listener = None
        self._stop_event = threading.Event() # Use threading.Event for stopping
        # pynput controller for non-windows simulation fallback
        try:
            self.kb_controller = keyboard.Controller()
        except Exception as e:
            print(f"[Hotkey Worker] Error initializing pynput keyboard controller: {e}")
            self.kb_controller = None

    # --- Windows Specific Copy Simulation (using SendInput) ---
    def _simulate_copy_windows(self):
        """Simulates Ctrl+C using ctypes SendInput with timing that works in other apps."""
        if not ctypes or not IS_WINDOWS: # Double-check IS_WINDOWS in case structure definition failed
            print("[Hotkey Worker] ctypes/SendInput simulation unavailable.")
            return False

        print("[Hotkey Worker] Simulating Copy command using SendInput (Ctrl+C) with revised timing...")
        success = False
        try:
            # Create Input event structures
            ctrl_down = Input(type=INPUT_KEYBOARD, ii=Input_I(ki=KeyBdInput(wVk=VK_CONTROL, dwFlags=0)))
            c_down = Input(type=INPUT_KEYBOARD, ii=Input_I(ki=KeyBdInput(wVk=VK_C, dwFlags=0)))
            c_up = Input(type=INPUT_KEYBOARD, ii=Input_I(ki=KeyBdInput(wVk=VK_C, dwFlags=KEYEVENTF_KEYUP)))
            ctrl_up = Input(type=INPUT_KEYBOARD, ii=Input_I(ki=KeyBdInput(wVk=VK_CONTROL, dwFlags=KEYEVENTF_KEYUP)))

            # Prepare the array of events
            inputs = (Input * 4)(ctrl_down, c_down, c_up, ctrl_up) # Create array

            # Send Ctrl Down + C Down
            print("[Hotkey Worker] Sending Ctrl Down, C Down...")
            ctypes.windll.user32.SendInput(2, ctypes.pointer(inputs[0]), ctypes.sizeof(Input))

            # Wait
            time.sleep(0.05)  # Use 0.05s delay that works in other app

            # Send C Up + Ctrl Up
            print("[Hotkey Worker] Sending C Up, Ctrl Up...")
            ctypes.windll.user32.SendInput(2, ctypes.pointer(inputs[2]), ctypes.sizeof(Input))

            print("[Hotkey Worker] SendInput Copy simulation sequence sent.")
            success = True
        except Exception as e:
            print(f"[Hotkey Worker] Error during SendInput copy simulation: {e}")
            self.error_occurred.emit(f"SendInput Copy simulation failed: {e}")
            success = False
            # Attempt cleanup in case of error during sequence
            try:
                 print("[Hotkey Worker] Attempting SendInput cleanup...")
                 inputs_cleanup = (Input * 2)(c_up, ctrl_up)
                 ctypes.windll.user32.SendInput(2, ctypes.pointer(inputs_cleanup[0]), ctypes.sizeof(Input))
            except Exception as cleanup_e:
                 print(f"[Hotkey Worker] Error during SendInput cleanup attempt: {cleanup_e}")
        finally:
            # Use shorter delay that works in other app
            print("[Hotkey Worker] Waiting for clipboard update (after SendInput)...")
            time.sleep(0.1)  # Use 0.1s delay from working implementation
            print("[Hotkey Worker] Clipboard wait finished.")
            return success
    # --- End Windows Specific ---

    # --- pynput based simulation (Fallback/Non-Windows) ---
    def _simulate_copy_pynput(self):
        """Attempts to simulate copy using pynput controller with timing that works in other apps."""
        if not self.kb_controller:
            print("[Hotkey Worker] pynput Keyboard controller not available.")
            return False

        copy_modifier_key = keyboard.Key.cmd if platform.system() == "Darwin" else keyboard.Key.ctrl
        print(f"[Hotkey Worker] Attempting to simulate Copy command using pynput ({copy_modifier_key} + C) with revised timing...")
        success = False
        try:
            self.kb_controller.press(copy_modifier_key)
            self.kb_controller.press('c')
            time.sleep(0.05)  # Use 0.05s delay that works in other app
            self.kb_controller.release('c')
            self.kb_controller.release(copy_modifier_key)
            print("[Hotkey Worker] pynput Copy simulation key sequence sent.")
            success = True
        except Exception as e:
            print(f"[Hotkey Worker] Error during pynput copy simulation: {e}")
            try: # Attempt cleanup
                self.kb_controller.release('c')
                self.kb_controller.release(copy_modifier_key)
            except: pass
            self.error_occurred.emit(f"pynput Copy simulation failed: {e}")
            success = False
        finally:
            print("[Hotkey Worker] Waiting for clipboard update (after pynput)...")
            time.sleep(0.1)  # Use 0.1s delay from working implementation
            print("[Hotkey Worker] Clipboard wait finished.")
            return success
    # --- End pynput simulation ---

    def _simulate_copy_combined(self):
        """Tries both copy methods sequentially for better reliability."""
        print("[Hotkey Worker] Running both copy simulation methods for maximum reliability...")
        overall_success = False
        
        # Try Windows method if available
        windows_success = False
        if IS_WINDOWS and ctypes:
            print("[Hotkey Worker] Running Windows SendInput method...")
            windows_success = self._simulate_copy_windows()
            if windows_success:
                overall_success = True
                print("[Hotkey Worker] Windows SendInput method succeeded")
            else:
                print("[Hotkey Worker] Windows SendInput method failed")
        
        # Always try pynput method regardless of Windows method result
        pynput_success = False
        if self.kb_controller:
            print("[Hotkey Worker] Running pynput method (regardless of previous result)...")
            pynput_success = self._simulate_copy_pynput()
            if pynput_success:
                overall_success = True
                print("[Hotkey Worker] pynput method succeeded")
            else:
                print("[Hotkey Worker] pynput method failed")
        
        print(f"[Hotkey Worker] Combined copy simulation results: Windows={windows_success}, pynput={pynput_success}, overall={'Success' if overall_success else 'Failed'}")
        return overall_success

    def _get_callback(self, signal_name):
        """Returns a function that emits the corresponding signal."""
        def callback():
            print(f"[Hotkey Worker] Hotkey triggered: {signal_name}")

            # Simulate copy ONLY for quick_add_rule
            # ---> REMOVE THE COPY SIMULATION FROM HERE <---
            # if signal_name == 'quick_add_rule_triggered':
            #     # Use combined approach for better reliability
            #     self._simulate_copy_combined()
                # NOTE: Proceed to emit signal regardless of simulation success

            # Emit the original signal
            try:
                signal = getattr(self, signal_name)
                if signal:
                    signal.emit()
                else:
                    print(f"[Hotkey Worker] Error: Signal '{signal_name}' not found.")
            except Exception as e:
                print(f"[Hotkey Worker] Error emitting signal {signal_name}: {e}")
        return callback

    def run(self):
        """Starts the pynput listener."""
        print("[Hotkey Worker] Listener thread started.")
        callbacks = {}
        if not self.hotkey_map:
             print("[Hotkey Worker] No hotkeys registered.")
             self.error_occurred.emit("No hotkeys configured.") # Inform main thread
             return # Exit if no hotkeys

        # Check if simulation is possible if needed
        quick_add_active = any(s == 'quick_add_rule_triggered' for s in self.hotkey_map.values())
        simulation_possible = (IS_WINDOWS and ctypes) or (not IS_WINDOWS and self.kb_controller)
        if quick_add_active and not simulation_possible:
             print("[Hotkey Worker] Warning: Quick Add hotkey active, but copy simulation unavailable for this platform/setup.")

        try:
            for combo, signal_name in self.hotkey_map.items():
                callback_func = self._get_callback(signal_name)
                if callback_func:
                    callbacks[combo] = callback_func
            print(f"[Hotkey Worker] Registering hotkeys: {list(callbacks.keys())}")

            # Use GlobalHotKeys listener
            # Pass callbacks directly
            self.listener = keyboard.GlobalHotKeys(callbacks)
            self.listener.start() # Start listening in this thread

            # Keep the thread alive while listening and check for stop signal
            while not self._stop_event.is_set() and self.listener.is_alive():
                time.sleep(0.1) # Prevent busy-waiting

        except Exception as e:
            error_msg = f"Error starting hotkey listener: {e}"
            print(f"[Hotkey Worker] {error_msg}")
            self.error_occurred.emit(error_msg)
            # Ensure listener is stopped if partially started
            if self.listener and hasattr(self.listener, 'stop'):
                try:
                     self.listener.stop()
                except Exception as stop_e:
                     print(f"[Hotkey Worker] Error stopping listener after exception: {stop_e}")
            self.listener = None

        finally:
            # Ensure cleanup happens when loop exits (either by stop signal or error)
            if self.listener and self.listener.is_alive():
                try:
                     self.listener.stop()
                     print("[Hotkey Worker] Listener stopped.")
                except Exception as e:
                     print(f"[Hotkey Worker] Error stopping listener during cleanup: {e}")
            self.listener = None
            print("[Hotkey Worker] Listener thread finished.")

    def stop(self):
        """Signals the listener thread to stop."""
        print("[Hotkey Worker] Stop requested.")
        self._stop_event.set()


class HotkeyManager(QObject):
    """Manages global hotkey registration and listening using pynput."""
    # Proxy signals from the worker
    toggle_engine_triggered = Signal()
    show_hide_triggered = Signal()
    next_profile_triggered = Signal()
    prev_profile_triggered = Signal()
    quick_add_rule_triggered = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_hotkey_map = {} # {pynput_combo_str: signal_name_str}
        self._listener_thread = None
        self._listener_worker = None
        self._stopping_flag = threading.Event() # Use an event for clearer stop signalling

    def update_hotkeys(self, hotkey_map: dict):
        """Stops existing listener safely, updates map, and starts new listener."""
        print(f"[HotkeyManager] Updating hotkeys: {hotkey_map}")

        # --- Stop and wait for the old listener ---
        self.stop_listener()
        # ---

        # --- Create and start the new listener ---
        self.current_hotkey_map = hotkey_map
        if not self.current_hotkey_map:
             print("[HotkeyManager] No hotkeys to register.")
             return

        self._stopping_flag.clear() # Ensure flag is clear before starting new thread
        self._listener_worker = HotkeyListenerWorker(self.current_hotkey_map)
        self._listener_thread = QThread() # Use QThread for better Qt integration

        # Move worker to the thread
        self._listener_worker.moveToThread(self._listener_thread)

        # Connect worker signals to manager signals (proxying)
        self._listener_worker.toggle_engine_triggered.connect(self.toggle_engine_triggered)
        self._listener_worker.show_hide_triggered.connect(self.show_hide_triggered)
        self._listener_worker.next_profile_triggered.connect(self.next_profile_triggered)
        self._listener_worker.prev_profile_triggered.connect(self.prev_profile_triggered)
        self._listener_worker.quick_add_rule_triggered.connect(self.quick_add_rule_triggered)
        self._listener_worker.error_occurred.connect(self.error_occurred)

        # Connect thread started signal to worker's run method
        self._listener_thread.started.connect(self._listener_worker.run)

        # Connect thread finished signal for cleanup
        self._listener_thread.finished.connect(lambda: self._handle_thread_finish(self._listener_worker, self._listener_thread))

        # Start the thread
        self._listener_thread.start()
        print("[HotkeyManager] New listener thread started.")
        # ---

    def stop_listener(self):
        """Stops the current listener thread safely and waits for it."""
        if self._stopping_flag.is_set():
             print("[HotkeyManager] Already in process of stopping.")
             return # Avoid concurrent stops

        if not self._listener_thread or not self._listener_thread.isRunning():
            print("[HotkeyManager] No active listener thread to stop.")
            self._clear_refs() # Ensure refs are clear if called when stopped
            return

        print("[HotkeyManager] Attempting to stop listener thread...")
        self._stopping_flag.set() # Signal that we are stopping

        # Keep local references for cleanup
        thread_to_stop = self._listener_thread
        worker_to_stop = self._listener_worker

        # Clear instance references immediately
        self._listener_thread = None
        self._listener_worker = None

        try:
            # Signal worker loop to exit first
            if worker_to_stop:
                print("[HotkeyManager] Signaling worker to stop...")
                worker_to_stop.stop() # Signal the pynput listener loop to break

            # Request QThread to quit
            print("[HotkeyManager] Requesting QThread quit...")
            thread_to_stop.quit()

            # Wait for QThread to finish
            print("[HotkeyManager] Waiting for QThread to finish...")
            if not thread_to_stop.wait(3000): # Wait up to 3 seconds
                print("[HotkeyManager] Warning: Listener QThread did not finish gracefully. Terminating.")
                thread_to_stop.terminate() # Force if necessary
                thread_to_stop.wait(1000) # Wait after termination
            else:
                print("[HotkeyManager] Listener QThread finished gracefully.")

            # Schedule worker object deletion (now that thread is stopped)
            if worker_to_stop:
                print("[HotkeyManager] Scheduling old worker for deletion...")
                worker_to_stop.deleteLater()

        except Exception as e:
             print(f"[HotkeyManager] Exception during stop_listener: {e}")
        finally:
            self._stopping_flag.clear() # Clear the flag after attempt
            print("[HotkeyManager] stop_listener sequence finished.")

    def _handle_thread_finish(self, worker, thread):
        """Cleanup handler connected to thread.finished signal."""
        print("[HotkeyManager] Listener thread finished signal received.")
        if worker:
             worker.deleteLater()
        # Thread object connected to this signal will be automatically cleaned up by Qt if deleteLater was called on it previously,
        # or garbage collected by Python if no other references exist. We mainly need to ensure the worker is deleted.
        # Check if this cleanup corresponds to the *current* references, clear if so.
        if self._listener_thread is thread:
             print("[HotkeyManager] Clearing potentially stale thread/worker references on finish.")
             self._clear_refs()

    def _clear_refs(self):
         """Internal helper to clear references."""
         self._listener_thread = None
         self._listener_worker = None

    def is_listening(self) -> bool:
        """Check if the listener thread reference exists and is running."""
        # Check the instance variable which points to the *current* intended thread
        return self._listener_thread is not None and self._listener_thread.isRunning() 