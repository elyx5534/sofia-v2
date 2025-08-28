"""
Symbol mapping utilities for unified WS/REST/UI symbols
"""

import json
import os
from pathlib import Path
from typing import Optional


class SymbolMapper:
    """Handles symbol mapping between UI, WebSocket, and REST formats"""
    
    def __init__(self):
        config_path = Path(__file__).parent.parent / 'config' / 'symbol_map.json'
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.mappings = self.config.get('mappings', {})
    
    def get_ws_sym(self, ui_sym: str) -> Optional[str]:
        """Get WebSocket symbol from UI symbol"""
        if ui_sym in self.mappings:
            return self.mappings[ui_sym].get('ws')
        
        # Try reverse lookup
        for key, mapping in self.mappings.items():
            if mapping.get('ui') == ui_sym:
                return mapping.get('ws')
        
        return None
    
    def get_rest_sym(self, ui_sym: str) -> Optional[str]:
        """Get REST API symbol from UI symbol"""
        if ui_sym in self.mappings:
            return self.mappings[ui_sym].get('rest')
        
        # Try reverse lookup
        for key, mapping in self.mappings.items():
            if mapping.get('ui') == ui_sym:
                return mapping.get('rest')
        
        return None
    
    def get_ui_sym(self, ws_or_rest_sym: str) -> Optional[str]:
        """Get UI symbol from WebSocket or REST symbol"""
        if ws_or_rest_sym in self.mappings:
            return self.mappings[ws_or_rest_sym].get('ui')
        
        # Try reverse lookup
        for key, mapping in self.mappings.items():
            if mapping.get('ws') == ws_or_rest_sym or mapping.get('rest') == ws_or_rest_sym:
                return mapping.get('ui')
        
        return None


# Global instance
symbol_mapper = SymbolMapper()


# Convenience functions
def get_ws_sym(ui_sym: str) -> Optional[str]:
    """Get WebSocket symbol from UI symbol"""
    return symbol_mapper.get_ws_sym(ui_sym)


def get_rest_sym(ui_sym: str) -> Optional[str]:
    """Get REST API symbol from UI symbol"""
    return symbol_mapper.get_rest_sym(ui_sym)