import tkinter as tk
from tkinter import Frame, Canvas, Label
import threading
import obspython as obs
import os
import math

# --- Configuration Globals ---
overlay_position = "top_right"
slide_from = "none"
offset_x = 0
offset_y = 0
overlay_width = 0
overlay_height = 0
overlay_size = 64
icon_padding = 10
slide_steps = 10
slide_interval = 30
display_time = 2000
default_font_size = 11
persistent_overlay = False
style_mode = "image_text"

# --- Icon Paths & Objects ---
icon_rec_start_path = ""
icon_rec_saved_path = ""
icon_rec_paused_path = ""
icon_rec_resumed_path = ""

icon_rec_start = None
icon_rec_saved = None
icon_rec_paused = None
icon_rec_resumed = None

app_instance = None
thd = None
margin = 20
record_active = False

# --- Main Overlay Class ---
class Application(tk.Tk):
	def __init__(self):
		super().__init__()
		self.attributes('-topmost', True)
		self.overrideredirect(True)
		self.configure(bg='#000000')
		self.attributes('-transparentcolor', '#000000')
		self.attributes('-alpha', 0.0)
		self.container = Frame(self, bg='#333333', bd=2, relief='ridge')
		self.container.pack()
		global canvas, label
		canvas = Canvas(self.container, bg='#333333', highlightthickness=0)
		canvas.grid(row=0, column=0)
		label = Label(self.container, text='', font=('Roboto', default_font_size, 'bold'),
						bg='#333333', fg='#ffffff')
		label.grid(row=0, column=1)

	def compute_content_size(self):
		self.container.update_idletasks()
		w = overlay_width or self.container.winfo_reqwidth()
		h = overlay_height or self.container.winfo_reqheight()
		return w, h

	def compute_position(self, w, h):
		sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
		if overlay_position == 'top_left':
			x, y = margin, margin
		elif overlay_position == 'bottom_left':
			x, y = margin, sh - h - margin
		elif overlay_position == 'bottom_right':
			x, y = sw - w - margin, sh - h - margin
		else:
			x, y = sw - w - margin, margin
		x += offset_x; y += offset_y
		x = max(margin, min(x, sw - w - margin))
		y = max(margin, min(y, sh - h - margin))
		return x, y

	def slide_to(self, w, h, fx, fy):
		if slide_from == 'none' or slide_steps <= 0:
			self.geometry(f"{w}x{h}+{fx}+{fy}")
			self.attributes('-alpha', 0.95)
			return
		if slide_from == 'left':
			sx, sy = -w, fy
		elif slide_from == 'right':
			sx, sy = self.winfo_screenwidth(), fy
		elif slide_from == 'top':
			sx, sy = fx, -h
		else:
			sx, sy = fx, self.winfo_screenheight()
		steps = max(1, slide_steps)
		dx, dy = (fx - sx) / steps, (fy - sy) / steps
		self._anim_step = 0
		self._anim_steps = steps
		self._sx, self._sy, self._dx, self._dy = sx, sy, dx, dy
		self._anim_wh = (w, h)
		self.geometry(f"{w}x{h}+{int(sx)}+{int(sy)}")
		self.attributes('-alpha', 0.95)
		self.after(slide_interval, self._anim_step_func)

	def _anim_step_func(self):
		w, h = self._anim_wh
		if self._anim_step < self._anim_steps:
			x = self._sx + self._dx * (self._anim_step + 1)
			y = self._sy + self._dy * (self._anim_step + 1)
			self.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
			self._anim_step += 1
			self.after(slide_interval, self._anim_step_func)

	def show_notification(self, typ, state):
		load_icons()
		canvas.delete('all')
		label.grid()
		canvas.grid()
		
		# --- Determine Text and Icon based on state ---
		text_to_show = ""
		img = None
		color_fill = '#E71D36' # Default red
		
		if state == 'saved':
			text_to_show = 'Recording Saved'
			img = icon_rec_saved
			color_fill = '#06D6A0'
		elif state == 'paused':
			text_to_show = 'Recording Paused'
			img = icon_rec_paused
			color_fill = '#FFD166'
		elif state == 'resumed':
			text_to_show = 'Recording Resumed'
			img = icon_rec_resumed
			color_fill = '#E71D36'
		elif state == 'started' or record_active:
			text_to_show = 'Recording Started'
			img = icon_rec_start
			color_fill = '#E71D36'
		else:
			return self.fade_out()

		# --- Apply to UI ---
		label.config(text=text_to_show)
		
		if img:
			canvas.config(width=img.width(), height=img.height())
			canvas.create_image(img.width()//2, img.height()//2, image=img)
		else:
			# Fallback if no icon selected: Draw a simple shape
			canvas.config(width=overlay_size, height=overlay_size)
			symbol = '●'
			if state == 'saved': symbol = '✔'
			if state == 'paused': symbol = '⏸'
			if state == 'resumed': symbol = '▶'
			
			canvas.create_text(overlay_size//2, overlay_size//2,
								text=symbol, fill=color_fill,
								font=('Segoe UI', overlay_size//2, 'bold'))

		# --- Animation ---
		w, h = self.compute_content_size()
		fx, fy = self.compute_position(w, h)
		self.slide_to(w, h, fx, fy)
		
		if state == 'started' and persistent_overlay:
			pass
		else:
			self.after(display_time, self._after_saved)

	def _after_saved(self):
		if record_active and persistent_overlay:
			self.show_notification('recording', 'started')
		else:
			self.fade_out()

	def fade_out(self):
		a = self.attributes('-alpha')
		if a > 0.1:
			self.attributes('-alpha', a - 0.05)
			self.after(30, self.fade_out)
		else:
			self.attributes('-alpha', 0.0)

# --- Helpers ---
def load_and_scale(path):
	if not path or not os.path.isfile(path):
		return None
	try:
		img = tk.PhotoImage(file=path)
	except:
		return None
	w, h = img.width(), img.height()
	if overlay_size and max(w, h) > overlay_size:
		factor = math.ceil(max(w, h) / overlay_size)
		img = img.subsample(factor, factor)
	return img

def load_icons():
	global icon_rec_start, icon_rec_saved, icon_rec_paused, icon_rec_resumed
	icon_rec_start   = load_and_scale(icon_rec_start_path)
	icon_rec_saved   = load_and_scale(icon_rec_saved_path)
	icon_rec_paused  = load_and_scale(icon_rec_paused_path)
	icon_rec_resumed = load_and_scale(icon_rec_resumed_path)

def runtk():
	global app_instance
	app_instance = Application()
	load_icons()
	app_instance.mainloop()
	app_instance = None

def start_thread():
	global thd
	if not thd or not thd.is_alive():
		thd = threading.Thread(target=runtk, daemon=True)
		thd.start()

# --- OBS Event Handler ---
def frontend_event_handler(evt):
	global app_instance, record_active
	
	# === FIX FOR CRASHING: Cleanly close Tkinter when OBS closes ===
	if evt == obs.OBS_FRONTEND_EVENT_EXIT:
		if app_instance:
			app_instance.quit()
		return
	# ===============================================================

	if evt == obs.OBS_FRONTEND_EVENT_FINISHED_LOADING:
		start_thread()
		return
	if not app_instance:
		return

	mapping = {
		obs.OBS_FRONTEND_EVENT_RECORDING_STARTING: ('recording', 'started', True),
		obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED:  ('recording', 'saved',   False),
		obs.OBS_FRONTEND_EVENT_RECORDING_PAUSED:   ('recording', 'paused',  True),
		obs.OBS_FRONTEND_EVENT_RECORDING_UNPAUSED: ('recording', 'resumed', True),
	}

	if evt in mapping:
		typ, state, active = mapping[evt]
		record_active = active
		app_instance.after(0, lambda t=typ, s=state: app_instance.show_notification(t, s))

def script_description():
	return "Simple Recording Notifications (Start/Save/Pause/Resume). Fixed crashing issues."

def script_defaults(settings):
	obs.obs_data_set_default_string(settings, "p_rec_start", "")
	obs.obs_data_set_default_string(settings, "p_rec_saved", "")
	obs.obs_data_set_default_string(settings, "p_rec_paused", "")
	obs.obs_data_set_default_string(settings, "p_rec_resumed", "")
	
	obs.obs_data_set_default_int(settings, "p_overlay_size", 20)
	obs.obs_data_set_default_int(settings, "p_icon_padding", 5)
	obs.obs_data_set_default_int(settings, "p_overlay_width", 0)
	obs.obs_data_set_default_int(settings, "p_overlay_height", 0)
	obs.obs_data_set_default_int(settings, "p_offset_x", 0)
	obs.obs_data_set_default_int(settings, "p_offset_y", 0)
	obs.obs_data_set_default_int(settings, "p_slide_steps", 35)
	obs.obs_data_set_default_int(settings, "p_slide_interval", 10)
	obs.obs_data_set_default_int(settings, "p_font_size", default_font_size)
	obs.obs_data_set_default_string(settings, "p_overlay_position", "top_right")
	obs.obs_data_set_default_string(settings, "p_slide_from", "right")
	obs.obs_data_set_default_bool(settings, "p_persistent", False)

def script_properties():
	props = obs.obs_properties_create()
	
	obs.obs_properties_add_path(props, "p_rec_start", "Recording Started Icon", obs.OBS_PATH_FILE, "*.png;*.gif;*.jpg", None)
	obs.obs_properties_add_path(props, "p_rec_saved", "Recording Saved Icon", obs.OBS_PATH_FILE, "*.png;*.gif;*.jpg", None)
	obs.obs_properties_add_path(props, "p_rec_paused", "Recording Paused Icon", obs.OBS_PATH_FILE, "*.png;*.gif;*.jpg", None)
	obs.obs_properties_add_path(props, "p_rec_resumed", "Recording Resumed Icon", obs.OBS_PATH_FILE, "*.png;*.gif;*.jpg", None)
	
	obs.obs_properties_add_int(props, "p_overlay_size", "Max icon size (px)", 1, 512, 1)
	obs.obs_properties_add_int(props, "p_icon_padding", "Padding between icons (px)", 0, 50, 1)
	obs.obs_properties_add_int(props, "p_overlay_width", "Overlay width (px, 0=auto)", 0, 1920, 1)
	obs.obs_properties_add_int(props, "p_overlay_height", "Overlay height (px, 0=auto)", 0, 1080, 1)
	obs.obs_properties_add_int(props, "p_offset_x", "Offset X (px)", -500, 500, 1)
	obs.obs_properties_add_int(props, "p_offset_y", "Offset Y (px)", -500, 500, 1)
	obs.obs_properties_add_int(props, "p_slide_steps", "Slide steps", 1, 100, 1)
	obs.obs_properties_add_int(props, "p_slide_interval", "Slide interval (ms)", 1, 1000, 10)
	
	pos = obs.obs_properties_add_list(props, "p_overlay_position", "Overlay position", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
	for txt, val in [("Top Right","top_right"),("Top Left","top_left"), ("Bottom Left","bottom_left"),("Bottom Right","bottom_right")]:
		obs.obs_property_list_add_string(pos, txt, val)
		
	frm = obs.obs_properties_add_list(props, "p_slide_from", "Slide from", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
	for txt, val in [("None","none"),("Left","left"),("Right","right"), ("Top","top"),("Bottom","bottom")]:
		obs.obs_property_list_add_string(frm, txt, val)
		
	obs.obs_properties_add_int(props, "p_font_size", "Font Size", 6, 72, 1)
	obs.obs_properties_add_bool(props, "p_persistent", "Keep overlay (Always show 'Started')")

	return props

def script_update(settings):
	global icon_rec_start_path, icon_rec_saved_path, icon_rec_paused_path, icon_rec_resumed_path
	global overlay_size, icon_padding, overlay_width, overlay_height
	global offset_x, offset_y, slide_steps, slide_interval
	global overlay_position, slide_from, default_font_size
	global persistent_overlay

	icon_rec_start_path = obs.obs_data_get_string(settings, "p_rec_start")
	icon_rec_saved_path = obs.obs_data_get_string(settings, "p_rec_saved")
	icon_rec_paused_path = obs.obs_data_get_string(settings, "p_rec_paused")
	icon_rec_resumed_path = obs.obs_data_get_string(settings, "p_rec_resumed")
	
	overlay_size = obs.obs_data_get_int(settings, "p_overlay_size")
	icon_padding = obs.obs_data_get_int(settings, "p_icon_padding")
	overlay_width = obs.obs_data_get_int(settings, "p_overlay_width")
	overlay_height = obs.obs_data_get_int(settings, "p_overlay_height")
	offset_x = obs.obs_data_get_int(settings, "p_offset_x")
	offset_y = obs.obs_data_get_int(settings, "p_offset_y")
	slide_steps = obs.obs_data_get_int(settings, "p_slide_steps")
	slide_interval = obs.obs_data_get_int(settings, "p_slide_interval")
	overlay_position = obs.obs_data_get_string(settings, "p_overlay_position")
	slide_from = obs.obs_data_get_string(settings, "p_slide_from")
	default_font_size = obs.obs_data_get_int(settings, "p_font_size")
	persistent_overlay = obs.obs_data_get_bool(settings, "p_persistent")
	
	if app_instance:
		app_instance.after(0, load_icons)

def script_load(settings):
	obs.obs_frontend_add_event_callback(frontend_event_handler)