"""Combine per-action attribute changes into one feature update."""


def merge_attribute_updates(*plans):
  """One edit per OBJECTID. Later fields on the same feature are added."""
  merged = {}
  for plan in plans:
    for object_id, attributes in plan.items():
      slot = merged.setdefault(object_id, {"OBJECTID": object_id})
      slot.update(attributes)
  return [{"attributes": attributes} for attributes in merged.values()]
