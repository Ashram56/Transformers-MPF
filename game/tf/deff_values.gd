extends "res://tf/rom_screen.gd"
## The printf texts of a captured display effect (scripts/gen_media.py value_texts), drawn live over its frames.
## metadata "slots": [{"t", "f", "x", "y", "a", "source"}], the texts with the capture's string; metadata
## "frames": per animation frame of the sibling "Anim", the slots that frame shows (their dots are cleared
## from the frame). The event arg `values` (tf/media_bridge.py) holds the formatted text per slot; a slot the
## rules gave no value for keeps the capture's string.

var _slots: Array = []
var _frames: Array = []
var _texts: Array = []
var _anim: AnimatedSprite2D = null


func _ready() -> void:
	super._ready()
	_slots = JSON.parse_string(str(get_meta("slots", "[]")))
	_frames = JSON.parse_string(str(get_meta("frames", "[]")))
	_anim = get_parent().get_node_or_null("Anim")
	if _anim:
		_anim.frame_changed.connect(_redraw)
	_redraw()


func update(settings: Dictionary, kwargs: Dictionary = {}) -> void:
	var values = kwargs.get("values", settings.get("values", null))
	if values is String:
		values = JSON.parse_string(values)
	if values is Array:
		_texts = values
		_redraw()


func _redraw() -> void:
	var frame := _anim.frame if _anim else 0
	var items: Array = []
	if frame < _frames.size():
		for i in _frames[frame]:
			var s: Dictionary = _slots[int(i)]
			var t = s["t"]
			if int(i) < _texts.size() and _texts[int(i)] != null:
				t = _texts[int(i)]
			items.append({"t": t, "f": s["f"], "x": s["x"], "y": s["y"], "a": s["a"]})
	_draw_items(items)
