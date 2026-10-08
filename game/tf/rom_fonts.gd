extends RefCounted
## The ROM's DMD fonts in Godot (game/fonts, built by scripts/gen_fonts.py): metrics as the ROM measures text
## (text_width: glyph widths, x offsets and the spacing between glyphs) and the bitmap font files.

static var _metrics: Dictionary = {}
static var _font_files: Dictionary = {}


static func font_metrics(font_id: int) -> Dictionary:
	if _metrics.is_empty() and FileAccess.file_exists("res://fonts/fonts.json"):
		var data = JSON.parse_string(FileAccess.get_file_as_string("res://fonts/fonts.json"))
		for f in data["fonts"]:
			_metrics[int(f["id"])] = f
	return _metrics.get(font_id, {})


static func font_file(font_id: int) -> FontFile:
	if not _font_files.has(font_id):
		var f := FontFile.new()
		f.load_bitmap_font("res://fonts/rom_font_%02d.fnt" % font_id)
		_font_files[font_id] = f
	return _font_files[font_id]


static func rom_width(m: Dictionary, s: String) -> int:
	var w := 0
	var n := 0
	for c in s:
		if m["glyphs"].has(c):
			var g = m["glyphs"][c]
			w += int(g["w"]) + int(g["xoff"]) + int(m["spacing"])
			n += 1
	return w - int(m["spacing"]) if n else 0
