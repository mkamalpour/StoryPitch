# story/memory.py
"""
Story Memory System
Tracks NPCs, locations, events, and relationships for continuity
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from constants import MEMORY_MAX_EVENTS, MEMORY_MAX_DISCOVERIES, MEMORY_RECENT_EVENTS_KEEP

logger = logging.getLogger(__name__)


class StoryMemory:
    """
    Persistent memory system for story elements.
    Stores in world_state for database persistence.
    """
    
    def __init__(self, world_state: Dict[str, Any]):
        """
        Initialize memory system with world state.
        
        Args:
            world_state: The session's world_state dictionary
        """
        self.world_state = world_state
        self._ensure_memory_structure()
    
    def _ensure_memory_structure(self):
        """Ensure all memory structures exist in world_state"""
        if "memory" not in self.world_state:
            self.world_state["memory"] = {
                "npcs": {},  # name -> {description, personality, last_seen_step, interactions}
                "locations": {},  # name -> {description, visited_count, last_visited_step}
                "events": [],  # [{step, description, importance}]
                "relationships": {},  # npc_name -> {affinity, trust, notes}
                "inventory": [],  # [{item, description, acquired_step}]
                "discoveries": []  # [{step, discovery, significance}]
            }
    
    # ===== NPC Management =====
    
    def add_npc(self, name: str, description: str = "", personality: str = "", step: int = 0):
        """
        Add or update an NPC in memory.
        
        Args:
            name: NPC name
            description: Physical description or role
            personality: Personality traits
            step: Step number when first met
        """
        npcs = self.world_state["memory"]["npcs"]
        
        if name not in npcs:
            npcs[name] = {
                "description": description,
                "personality": personality,
                "first_met_step": step,
                "last_seen_step": step,
                "interactions": 0
            }
            logger.info(f"Added new NPC: {name}")
        else:
            # Update existing NPC
            npcs[name]["last_seen_step"] = step
            npcs[name]["interactions"] += 1
            if description:
                npcs[name]["description"] = description
            if personality:
                npcs[name]["personality"] = personality
            logger.debug(f"Updated NPC: {name} (interactions: {npcs[name]['interactions']})")
    
    def get_npc(self, name: str) -> Optional[Dict[str, Any]]:
        """Get NPC information"""
        return self.world_state["memory"]["npcs"].get(name)
    
    def get_all_npcs(self) -> Dict[str, Dict[str, Any]]:
        """Get all NPCs"""
        return self.world_state["memory"]["npcs"]
    
    def get_recent_npcs(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get most recently seen NPCs.
        
        Args:
            count: Number of NPCs to return
            
        Returns:
            List of NPC dictionaries with names
        """
        npcs = self.world_state["memory"]["npcs"]
        sorted_npcs = sorted(
            npcs.items(),
            key=lambda x: x[1].get("last_seen_step", 0),
            reverse=True
        )
        
        result = []
        for name, data in sorted_npcs[:count]:
            result.append({"name": name, **data})
        
        return result
    
    # ===== Location Management =====
    
    def add_location(self, name: str, description: str = "", step: int = 0):
        """
        Add or update a location in memory.
        
        Args:
            name: Location name
            description: Location description
            step: Step number when visited
        """
        locations = self.world_state["memory"]["locations"]
        
        if name not in locations:
            locations[name] = {
                "description": description,
                "first_visited_step": step,
                "last_visited_step": step,
                "visited_count": 1
            }
            logger.info(f"Added new location: {name}")
        else:
            # Update existing location
            locations[name]["last_visited_step"] = step
            locations[name]["visited_count"] += 1
            if description:
                locations[name]["description"] = description
            logger.debug(f"Updated location: {name} (visits: {locations[name]['visited_count']})")
    
    def get_location(self, name: str) -> Optional[Dict[str, Any]]:
        """Get location information"""
        return self.world_state["memory"]["locations"].get(name)
    
    def get_all_locations(self) -> Dict[str, Dict[str, Any]]:
        """Get all locations"""
        return self.world_state["memory"]["locations"]
    
    def get_recent_locations(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get most recently visited locations.
        
        Args:
            count: Number of locations to return
            
        Returns:
            List of location dictionaries with names
        """
        locations = self.world_state["memory"]["locations"]
        sorted_locations = sorted(
            locations.items(),
            key=lambda x: x[1].get("last_visited_step", 0),
            reverse=True
        )
        
        result = []
        for name, data in sorted_locations[:count]:
            result.append({"name": name, **data})
        
        return result
    
    # ===== Event Management =====
    
    def add_event(self, description: str, step: int, importance: str = "normal"):
        """
        Record a significant event.
        
        Args:
            description: Event description
            step: Step number when event occurred
            importance: "low", "normal", "high", "critical"
        """
        events = self.world_state["memory"]["events"]
        
        event = {
            "step": step,
            "description": description,
            "importance": importance,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        events.append(event)
        logger.info(f"Recorded {importance} event at step {step}: {description[:50]}...")
        
        # Keep only last N events to prevent bloat (configurable via constants)
        if len(events) > MEMORY_MAX_EVENTS:
            # Keep all high/critical events, trim normal/low
            important_events = [e for e in events if e["importance"] in ["high", "critical"]]
            recent_events = events[-MEMORY_RECENT_EVENTS_KEEP:]  # Last N events
            self.world_state["memory"]["events"] = important_events + recent_events
    
    def get_events(self, importance: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get events, optionally filtered by importance.
        
        Args:
            importance: Filter by importance level (None = all)
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        events = self.world_state["memory"]["events"]
        
        if importance:
            events = [e for e in events if e["importance"] == importance]
        
        # Return most recent first
        return sorted(events, key=lambda x: x["step"], reverse=True)[:limit]
    
    # ===== Relationship Management =====
    
    def set_relationship(self, npc_name: str, affinity: int = 0, trust: int = 0, notes: str = ""):
        """
        Set or update relationship with an NPC.
        
        Args:
            npc_name: NPC name
            affinity: Affinity score (-100 to 100)
            trust: Trust score (-100 to 100)
            notes: Relationship notes
        """
        relationships = self.world_state["memory"]["relationships"]
        
        if npc_name not in relationships:
            relationships[npc_name] = {
                "affinity": affinity,
                "trust": trust,
                "notes": notes,
                "updated_step": 0
            }
            logger.info(f"Created relationship with {npc_name}")
        else:
            relationships[npc_name]["affinity"] = affinity
            relationships[npc_name]["trust"] = trust
            if notes:
                relationships[npc_name]["notes"] = notes
            logger.debug(f"Updated relationship with {npc_name}: affinity={affinity}, trust={trust}")
    
    def adjust_relationship(self, npc_name: str, affinity_change: int = 0, trust_change: int = 0):
        """
        Adjust relationship scores incrementally.
        
        Args:
            npc_name: NPC name
            affinity_change: Change in affinity (-100 to 100)
            trust_change: Change in trust (-100 to 100)
        """
        relationships = self.world_state["memory"]["relationships"]
        
        if npc_name not in relationships:
            self.set_relationship(npc_name, affinity_change, trust_change)
        else:
            rel = relationships[npc_name]
            rel["affinity"] = max(-100, min(100, rel["affinity"] + affinity_change))
            rel["trust"] = max(-100, min(100, rel["trust"] + trust_change))
            logger.debug(f"Adjusted relationship with {npc_name}: Δaffinity={affinity_change}, Δtrust={trust_change}")
    
    def get_relationship(self, npc_name: str) -> Optional[Dict[str, Any]]:
        """Get relationship with an NPC"""
        return self.world_state["memory"]["relationships"].get(npc_name)
    
    def get_all_relationships(self) -> Dict[str, Dict[str, Any]]:
        """Get all relationships"""
        return self.world_state["memory"]["relationships"]
    
    # ===== Inventory Management =====
    
    def add_item(self, item: str, description: str = "", step: int = 0):
        """
        Add item to inventory.
        
        Args:
            item: Item name
            description: Item description
            step: Step when acquired
        """
        inventory = self.world_state["memory"]["inventory"]
        
        # Check if item already exists
        for existing in inventory:
            if existing["item"].lower() == item.lower():
                logger.debug(f"Item already in inventory: {item}")
                return
        
        inventory.append({
            "item": item,
            "description": description,
            "acquired_step": step
        })
        logger.info(f"Added item to inventory: {item}")
    
    def remove_item(self, item: str) -> bool:
        """
        Remove item from inventory.
        
        Args:
            item: Item name
            
        Returns:
            True if item was removed, False if not found
        """
        inventory = self.world_state["memory"]["inventory"]
        
        for i, existing in enumerate(inventory):
            if existing["item"].lower() == item.lower():
                inventory.pop(i)
                logger.info(f"Removed item from inventory: {item}")
                return True
        
        return False
    
    def has_item(self, item: str) -> bool:
        """Check if item is in inventory"""
        inventory = self.world_state["memory"]["inventory"]
        return any(existing["item"].lower() == item.lower() for existing in inventory)
    
    def get_inventory(self) -> List[Dict[str, Any]]:
        """Get all inventory items"""
        return self.world_state["memory"]["inventory"]
    
    # ===== Discovery Management =====
    
    def add_discovery(self, discovery: str, significance: str = "normal", step: int = 0):
        """
        Record a discovery or revelation.
        
        Args:
            discovery: What was discovered
            significance: "minor", "normal", "major", "critical"
            step: Step when discovered
        """
        discoveries = self.world_state["memory"]["discoveries"]
        
        discoveries.append({
            "step": step,
            "discovery": discovery,
            "significance": significance
        })
        logger.info(f"Recorded {significance} discovery at step {step}: {discovery[:50]}...")
        
        # Keep only last N discoveries (configurable via constants)
        if len(discoveries) > MEMORY_MAX_DISCOVERIES:
            self.world_state["memory"]["discoveries"] = discoveries[-MEMORY_MAX_DISCOVERIES:]
    
    def get_discoveries(self, significance: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get discoveries, optionally filtered by significance.
        
        Args:
            significance: Filter by significance level (None = all)
            
        Returns:
            List of discovery dictionaries
        """
        discoveries = self.world_state["memory"]["discoveries"]
        
        if significance:
            discoveries = [d for d in discoveries if d["significance"] == significance]
        
        return discoveries
    
    # ===== Summary Methods =====
    
    def get_memory_summary(self) -> str:
        """
        Get a human-readable summary of all memory.
        Useful for debugging and UI display.
        
        Returns:
            Formatted summary string
        """
        npcs = self.get_all_npcs()
        locations = self.get_all_locations()
        events = self.get_events(limit=5)
        inventory = self.get_inventory()
        
        summary_parts = []
        
        if npcs:
            summary_parts.append(f"NPCs Met: {', '.join(npcs.keys())}")
        
        if locations:
            summary_parts.append(f"Locations Visited: {', '.join(locations.keys())}")
        
        if events:
            summary_parts.append(f"Recent Events: {len(events)} recorded")
        
        if inventory:
            items = [item["item"] for item in inventory]
            summary_parts.append(f"Inventory: {', '.join(items)}")
        
        return " | ".join(summary_parts) if summary_parts else "No memory recorded yet"
    
    def get_context_for_prompt(self) -> Dict[str, Any]:
        """
        Get memory context optimized for prompt generation.
        Returns only the most relevant information.
        
        Returns:
            Dictionary with memory context
        """
        return {
            "recent_npcs": self.get_recent_npcs(3),
            "recent_locations": self.get_recent_locations(3),
            "important_events": self.get_events(importance="high", limit=3),
            "inventory": self.get_inventory(),
            "key_relationships": {
                name: data for name, data in self.get_all_relationships().items()
                if abs(data.get("affinity", 0)) > 30 or abs(data.get("trust", 0)) > 30
            }
        }