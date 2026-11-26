extends Control
## A DMD screen drawn the way the ROM draws it: the event arg `draw` is a list of tf/rom_draw.py items, drawn in
## order over black:
## - {"t", "f", "x", "y", "a", "l"}: text t in ROM font f (game/fonts), baseline row y, a = flags (1 left edge
##   at x, 2 centred on x, 4 right edge at x), measured as the ROM measures it, at palette level l (0-15);
## - {"i", "x", "y"}: ROM image i (rom/mpf_package/media/rom_images_all.zip, img_NNNNN.png), top left at x, y;
## - {"r": [x, y, w, h], "l"}: a filled rectangle at palette level l (0-15);
## - {"i", "x", "y", "inv": true}: the image drawn through the service tests' palette (its empty dots lit);
## - {"chk": phase}: the DOT MATRIX TEST's checkerboard.

const RomFonts = preload("res://tf/rom_fonts.gd")
const DMD_COLOR := Color(1, 0.45, 0.05, 1)
const IMAGES_ZIP := "../rom/mpf_package/media/rom_images_all.zip"

static var _zip: ZIPReader = null
static var _textures: Dictionary = {}


func _ready() -> void:
	var slide = MPF.util.find_parent_slide_or_widget(self)
	if slide:
		slide.register_updater(self)


func _exit_tree() -> void:
	var slide = MPF.util.find_parent_slide_or_widget(self)
	if slide:
		slide.remove_updater(self)


func update(settings: Dictionary, kwargs: Dictionary = {}) -> void:
	var items = kwargs.get("draw", settings.get("draw", null))
	if items is String:
		items = JSON.parse_string(items)
	if items is Array:
		_draw_items(items)


static func texture(n: int) -> Texture2D:
	if _textures.has(n):
		return _textures[n]
	var tex: Texture2D = null
	if _zip == null:
		_zip = ZIPReader.new()
		if _zip.open(ProjectSettings.globalize_path("res://").path_join(IMAGES_ZIP)) != OK:
			push_warning("rom_screen: no %s" % IMAGES_ZIP)
	var bytes := _zip.read_file("img_%05d.png" % n) if _zip else PackedByteArray()
	if bytes.size():
		var img := Image.new()
		if img.load_png_from_buffer(bytes) == OK:
			tex = ImageTexture.create_from_image(img)
	_textures[n] = tex
	return tex


func _draw_items(items: Array) -> void:
	for child in get_children():
		remove_child(child)
		child.queue_free()
	for d in items:
		if not d is Dictionary:
			continue
		if d.has("t"):
			_add_text(str(d["t"]), int(d["f"]), int(d["x"]), int(d["y"]), int(d.get("a", 2)), int(d.get("l", 15)))
		elif d.has("i"):
			var tex := texture(int(d["i"]))
			if tex:
				var r := TextureRect.new()
				r.texture = tex
				r.position = Vector2(int(d["x"]), int(d["y"]))
				r.size = tex.get_size()
				r.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
				r.modulate = DMD_COLOR
				if d.get("inv", false):
					# drawn through the palette 0 -> 15 (the service tests' closed switch boxes, palette
					# 0x040c95c8): the image's empty dots lit behind its own dots
					var back := ColorRect.new()
					back.color = DMD_COLOR
					back.position = r.position
					back.size = r.size
					add_child(back)
					r.modulate = Color(0, 0, 0, 1)
				add_child(r)
		elif d.has("chk"):
			add_child(_checker(int(d["chk"])))
		elif d.has("r"):
			var rect := ColorRect.new()
			var level := int(d.get("l", 15)) / 15.0
			rect.color = Color(DMD_COLOR.r * level, DMD_COLOR.g * level, DMD_COLOR.b * level, 1)
			rect.position = Vector2(int(d["r"][0]), int(d["r"][1]))
			rect.size = Vector2(int(d["r"][2]), int(d["r"][3]))
			add_child(rect)


func _checker(phase: int) -> TextureRect:
	## The DOT MATRIX TEST's checkerboard [0x01047a50]: dot (x, y) lit when (x + y + phase) is odd.
	var img := Image.create_empty(128, 32, false, Image.FORMAT_RGBA8)
	for y in 32:
		for x in 128:
			img.set_pixel(x, y, DMD_COLOR if (x + y + phase) % 2 == 1 else Color(0, 0, 0, 1))
	var r := TextureRect.new()
	r.texture = ImageTexture.create_from_image(img)
	r.size = Vector2(128, 32)
	r.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	return r


func _add_text(s: String, font_id: int, x: int, y: int, flags: int, level: int = 15) -> void:
	var m: Dictionary = RomFonts.font_metrics(font_id)
	if m.is_empty():
		return
	var shown := ""
	for c in s:
		if m["glyphs"].has(c):
			shown += c
	if shown == "":
		return
	var w: int = RomFonts.rom_width(m, shown)
	var left := x
	if flags & 2:
		left = x - w / 2
	elif flags & 4:
		left = x + 1 - w
	var line_h := int(m["ascent"]) + int(m["descent"])
	var label := Label.new()
	label.text = shown
	label.clip_text = false
	label.autowrap_mode = TextServer.AUTOWRAP_OFF
	label.add_theme_font_override("font", RomFonts.font_file(font_id))
	label.add_theme_font_size_override("font_size", line_h)
	label.add_theme_constant_override("line_spacing", 0)
	label.add_theme_color_override("font_color", DMD_COLOR)
	label.position = Vector2(left, y - int(m["ascent"]) + 1)
	label.size = Vector2(maxi(w, 1) + 2, line_h)
	if level < 15:
		label.modulate = Color(level / 15.0, level / 15.0, level / 15.0, 1)
	add_child(label)
