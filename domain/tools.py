class Tool:
    def __init__(self, tool_type: str, diameter: float, coating: str = None):
        self.tool_type = tool_type
        self.diameter = diameter
        self.coating = coating or "none"

    def to_dict(self):
        return {
            "type": self.tool_type,
            "diameter": self.diameter,
            "coating": self.coating
        }
