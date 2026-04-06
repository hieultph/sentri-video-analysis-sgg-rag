"""
WebSocket handler for real-time communication between Stream Chat and Agno backend
"""
import asyncio
import json
import logging
from typing import Dict, Any, Set, Optional
from concurrent.futures import Future
from fastapi import WebSocket, WebSocketDisconnect
from stream_integration import stream_chat_manager

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manages WebSocket connections for real-time communication
    """
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}
        # Channel subscriptions
        self.channel_subscriptions: Dict[str, Set[str]] = {}
        # Event loop handling WebSocket tasks (set on first connection)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
    
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept WebSocket connection and add to active connections"""
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.loop = None
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connected",
            "client_id": client_id,
            "message": "Connected to Irrigation AI Assistant"
        }, client_id)
    
    def disconnect(self, client_id: str) -> None:
        """Remove WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        # Remove from channel subscriptions
        for channel_id, subscribers in self.channel_subscriptions.items():
            subscribers.discard(client_id)
        
        logger.info(f"WebSocket disconnected: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str) -> None:
        """Send message to specific client"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
    
    def send_personal_message_threadsafe(self, message: Dict[str, Any], client_id: str) -> bool:
        """Schedule a personal message from non-async contexts."""
        if not self.loop or not self.loop.is_running():
            logger.warning("Cannot send message thread-safely; WebSocket loop is unavailable")
            return False

        future: Future = asyncio.run_coroutine_threadsafe(
            self.send_personal_message(message, client_id),
            self.loop
        )
        def _report_error(fut: Future) -> None:
            exc = fut.exception()
            if exc:
                logger.error("Thread-safe send_personal_message failed: %s", exc)

        future.add_done_callback(_report_error)
        return True

    async def broadcast_to_channel(self, message: Dict[str, Any], channel_id: str) -> None:
        """Broadcast message to all clients subscribed to a channel"""
        if channel_id in self.channel_subscriptions:
            subscribers = self.channel_subscriptions[channel_id].copy()
            for client_id in subscribers:
                await self.send_personal_message(message, client_id)

    def broadcast_to_channel_threadsafe(self, message: Dict[str, Any], channel_id: str) -> bool:
        """Schedule a channel broadcast from non-async contexts."""
        if not self.loop or not self.loop.is_running():
            logger.warning("Cannot broadcast thread-safely; WebSocket loop is unavailable")
            return False

        future: Future = asyncio.run_coroutine_threadsafe(
            self.broadcast_to_channel(message, channel_id),
            self.loop
        )
        def _report_error(fut: Future) -> None:
            exc = fut.exception()
            if exc:
                logger.error("Thread-safe broadcast_to_channel failed: %s", exc)

        future.add_done_callback(_report_error)
        return True
    
    async def subscribe_to_channel(self, client_id: str, channel_id: str) -> None:
        """Subscribe client to a channel"""
        if channel_id not in self.channel_subscriptions:
            self.channel_subscriptions[channel_id] = set()
        
        self.channel_subscriptions[channel_id].add(client_id)
        logger.info(f"Client {client_id} subscribed to channel {channel_id}")
        
        # Send confirmation
        await self.send_personal_message({
            "type": "subscribed",
            "channel_id": channel_id,
            "message": f"Subscribed to channel {channel_id}"
        }, client_id)
    
    async def unsubscribe_from_channel(self, client_id: str, channel_id: str) -> None:
        """Unsubscribe client from a channel"""
        if channel_id in self.channel_subscriptions:
            self.channel_subscriptions[channel_id].discard(client_id)
            
        logger.info(f"Client {client_id} unsubscribed from channel {channel_id}")
        
        # Send confirmation
        await self.send_personal_message({
            "type": "unsubscribed",
            "channel_id": channel_id,
            "message": f"Unsubscribed from channel {channel_id}"
        }, client_id)
    
    async def handle_message(self, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message"""
        try:
            message_type = message_data.get("type")
            
            if message_type == "subscribe":
                channel_id = message_data.get("channel_id")
                if channel_id:
                    await self.subscribe_to_channel(client_id, channel_id)
            
            elif message_type == "unsubscribe":
                channel_id = message_data.get("channel_id")
                if channel_id:
                    await self.unsubscribe_from_channel(client_id, channel_id)
            
            elif message_type == "start_agent":
                await self.handle_start_agent(client_id, message_data)
            
            elif message_type == "stop_agent":
                await self.handle_stop_agent(client_id, message_data)
            
            elif message_type == "send_message":
                await self.handle_send_message(client_id, message_data)
            
            elif message_type == "get_agents":
                await self.handle_get_agents(client_id)
            
            elif message_type == "mobile_connect":
                await self.handle_mobile_connect(client_id, message_data)
            
            elif message_type == "mobile_message":
                await self.handle_mobile_message(client_id, message_data)
            
            else:
                await self.send_personal_message({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }, client_id)
        
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_personal_message({
                "type": "error",
                "message": f"Error processing message: {str(e)}"
            }, client_id)
    
    async def handle_mobile_connect(self, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle mobile app connection"""
        try:
            user_id = message_data.get("user_id")
            mission_id = message_data.get("mission_id")
            
            if not user_id or not mission_id:
                await self.send_personal_message({
                    "type": "error",
                    "message": "user_id and mission_id are required"
                }, client_id)
                return
            
            # Generate channel ID
            channel_id = f"ai-{user_id}-{mission_id}"
            
            # Subscribe to channel updates
            await self.subscribe_to_channel(client_id, channel_id)
            
            # Send confirmation
            await self.send_personal_message({
                "type": "mobile_connected",
                "user_id": user_id,
                "mission_id": mission_id,
                "channel_id": channel_id,
                "client_id": client_id,
                "message": "Mobile client connected successfully"
            }, client_id)
            
        except Exception as e:
            await self.send_personal_message({
                "type": "error",
                "message": f"Failed to connect mobile client: {str(e)}"
            }, client_id)
    
    async def handle_mobile_message(self, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle mobile message sending"""
        try:
            user_id = message_data.get("user_id")
            mission_id = message_data.get("mission_id")
            message_text = message_data.get("message")
            
            if not user_id or not mission_id or not message_text:
                await self.send_personal_message({
                    "type": "error",
                    "message": "user_id, mission_id, and message are required"
                }, client_id)
                return
            
            # Generate channel ID
            channel_id = f"ai-{user_id}-{mission_id}"
            
            # Send message to agent
            result = await stream_chat_manager.send_test_message(channel_id, message_text)
            
            if "error" in result:
                await self.send_personal_message({
                    "type": "error",
                    "message": result["error"]
                }, client_id)
            else:
                # Send response back to mobile client
                await self.send_personal_message({
                    "type": "mobile_ai_response",
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "mission_id": mission_id,
                    "user_message": message_text,
                    "ai_response": result["ai_response"],
                    "timestamp": asyncio.get_event_loop().time()
                }, client_id)
                
                # Also broadcast to channel subscribers
                await self.broadcast_to_channel({
                    "type": "mobile_ai_message",
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "mission_id": mission_id,
                    "message": result["ai_response"],
                    "timestamp": asyncio.get_event_loop().time()
                }, channel_id)
            
        except Exception as e:
            await self.send_personal_message({
                "type": "error",
                "message": f"Failed to send mobile message: {str(e)}"
            }, client_id)
    
    async def handle_start_agent(self, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle start agent request"""
        try:
            channel_id = message_data.get("channel_id")
            channel_type = message_data.get("channel_type", "messaging")
            
            if not channel_id:
                await self.send_personal_message({
                    "type": "error",
                    "message": "channel_id is required"
                }, client_id)
                return
            
            # Start agent
            result = await stream_chat_manager.start_agent(channel_id, channel_type)
            
            # Send response
            await self.send_personal_message({
                "type": "agent_started",
                "data": result
            }, client_id)
            
            # Broadcast to channel subscribers
            await self.broadcast_to_channel({
                "type": "agent_started",
                "data": result
            }, channel_id)
            
        except Exception as e:
            await self.send_personal_message({
                "type": "error",
                "message": f"Failed to start agent: {str(e)}"
            }, client_id)
    
    async def handle_stop_agent(self, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle stop agent request"""
        try:
            channel_id = message_data.get("channel_id")
            
            if not channel_id:
                await self.send_personal_message({
                    "type": "error",
                    "message": "channel_id is required"
                }, client_id)
                return
            
            # Stop agent
            result = await stream_chat_manager.stop_agent(channel_id)
            
            # Send response
            await self.send_personal_message({
                "type": "agent_stopped",
                "data": result
            }, client_id)
            
            # Broadcast to channel subscribers
            await self.broadcast_to_channel({
                "type": "agent_stopped",
                "data": result
            }, channel_id)
            
        except Exception as e:
            await self.send_personal_message({
                "type": "error",
                "message": f"Failed to stop agent: {str(e)}"
            }, client_id)
    
    async def handle_send_message(self, client_id: str, message_data: Dict[str, Any]) -> None:
        """Handle send message request"""
        try:
            channel_id = message_data.get("channel_id")
            message_text = message_data.get("message")
            
            if not channel_id or not message_text:
                await self.send_personal_message({
                    "type": "error",
                    "message": "channel_id and message are required"
                }, client_id)
                return
            
            # Send test message to agent
            result = await stream_chat_manager.send_test_message(channel_id, message_text)
            
            if "error" in result:
                await self.send_personal_message({
                    "type": "error",
                    "message": result["error"]
                }, client_id)
            else:
                # Send confirmation and response
                await self.send_personal_message({
                    "type": "message_response",
                    "channel_id": channel_id,
                    "user_message": message_text,
                    "ai_response": result["ai_response"]
                }, client_id)
                
                # Also broadcast to channel subscribers
                await self.broadcast_to_channel({
                    "type": "ai_message",
                    "channel_id": channel_id,
                    "message": result["ai_response"],
                    "user_id": f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
                }, channel_id)
            
        except Exception as e:
            await self.send_personal_message({
                "type": "error",
                "message": f"Failed to send message: {str(e)}"
            }, client_id)
    
    async def handle_get_agents(self, client_id: str) -> None:
        """Handle get active agents request"""
        try:
            agents = stream_chat_manager.get_active_agents()
            
            await self.send_personal_message({
                "type": "active_agents",
                "data": agents
            }, client_id)
            
        except Exception as e:
            await self.send_personal_message({
                "type": "error",
                "message": f"Failed to get agents: {str(e)}"
            }, client_id)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

async def handle_websocket_connection(websocket: WebSocket, client_id: str) -> None:
    """
    Main WebSocket connection handler
    """
    await websocket_manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle message
            await websocket_manager.handle_message(client_id, message_data)
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        logger.info(f"WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        websocket_manager.disconnect(client_id)
