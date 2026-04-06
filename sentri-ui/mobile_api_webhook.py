"""
Mobile API endpoints for irrigation assistant with TRUE WEBHOOK SUPPORT
Provides APIs for mobile app to interact with the irrigation AI system via Stream Chat webhooks
"""
import asyncio
import json
import logging
import re
import io
import sys
from contextlib import redirect_stdout
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import HTTPException
from pydantic import BaseModel
from stream_integration import stream_chat_manager
from websocket_handler import websocket_manager
from agents.assistant import get_assistant_agent

logger = logging.getLogger(__name__)

class MobileChannelRequest(BaseModel):
    user_id: str
    mission_id: str

class MobileChatMessage(BaseModel):
    user_id: str
    mission_id: str
    message: str

class MobileStreamMessage(BaseModel):
    user_id: str
    mission_id: str
    message: str
    stream_mode: str = "websocket"  # "websocket" or "sse" (Server-Sent Events)

class WebhookMobileChannelManager:
    """
    TRUE WEBHOOK-BASED Manager for mobile app channels and WebSocket connections
    This version uses real Stream Chat webhooks instead of simulated responses
    """
    
    def __init__(self):
        # Track mobile channels: {channel_id: {user_id, mission_id, websocket_client_id}}
        self.mobile_channels: Dict[str, Dict[str, Any]] = {}
        # Track user sessions: {user_id: {mission_id: channel_id}}
        self.user_sessions: Dict[str, Dict[str, str]] = {}
        # Store active agents for direct access (similar to app.py)
        self.active_mobile_agents: Dict[str, Any] = {}
        # Track pending messages waiting for webhook responses
        self.pending_messages: Dict[str, Dict[str, Any]] = {}
    
    def generate_channel_id(self, user_id: str, mission_id: str) -> str:
        """Generate channel ID for mobile app"""
        return f"ai-{user_id}-{mission_id}"
    
    def generate_websocket_client_id(self, user_id: str, mission_id: str) -> str:
        """Generate WebSocket client ID for mobile app"""
        return f"mobile-{user_id}-{mission_id}"
    
    def get_or_create_mobile_agent(self, user_id: str, mission_id: str) -> Any:
        """Get existing mobile agent or create new one for user+mission combination"""
        agent_key = f"{user_id}_{mission_id}"
        if agent_key not in self.active_mobile_agents:
            self.active_mobile_agents[agent_key] = get_assistant_agent(agent_key)
        return self.active_mobile_agents[agent_key]
    
    async def create_mobile_channel(self, user_id: str, mission_id: str) -> Dict[str, Any]:
        """
        Create a mobile channel for user and mission with TRUE WEBHOOK SUPPORT
        This will start an AI agent for the channel with webhook support
        """
        try:
            channel_id = self.generate_channel_id(user_id, mission_id)
            websocket_client_id = self.generate_websocket_client_id(user_id, mission_id)
            
            # Check if channel already exists
            if channel_id in self.mobile_channels:
                logger.info(f"Mobile channel {channel_id} already exists")
                return {
                    "status": "success",
                    "channel_id": channel_id,
                    "websocket_client_id": websocket_client_id,
                    "message": "Channel already exists",
                    "webhook_enabled": True
                }
            
            # Start AI agent for this channel with webhook support
            agent_result = await stream_chat_manager.start_agent(
                channel_id=channel_id,
                channel_type="messaging"
            )
            
            # Store channel information
            self.mobile_channels[channel_id] = {
                "user_id": user_id,
                "mission_id": mission_id,
                "websocket_client_id": websocket_client_id,
                "agent_user_id": agent_result.get("user_id"),
                "created_at": asyncio.get_event_loop().time(),
                "webhook_enabled": True
            }
            
            # Track user session
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = {}
            self.user_sessions[user_id][mission_id] = channel_id
            
            logger.info(f"Created mobile channel {channel_id} for user {user_id}, mission {mission_id} with webhook support")
            
            return {
                "status": "success",
                "channel_id": channel_id,
                "websocket_client_id": websocket_client_id,
                "agent_info": agent_result,
                "message": "Channel created successfully with webhook support",
                "webhook_enabled": True
            }
            
        except Exception as e:
            logger.error(f"Failed to create mobile channel: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create channel: {str(e)}")
    
    async def send_message_to_agent(self, user_id: str, mission_id: str, message: str) -> Dict[str, Any]:
        """
        Send message to AI agent via Stream Chat webhook flow (TRUE WEBHOOK)
        This uses real Stream Chat messages that trigger webhooks to our server
        """
        try:
            channel_id = self.generate_channel_id(user_id, mission_id)
            
            # Check if channel exists
            if channel_id not in self.mobile_channels:
                raise HTTPException(status_code=404, detail="Channel not found. Please create channel first.")
            
            channel_info = self.mobile_channels[channel_id]
            websocket_client_id = channel_info["websocket_client_id"]
            
            # Send message via Stream Chat (real webhook flow)
            mobile_user_id = f"mobile-{user_id}"
            result = await stream_chat_manager.send_user_message_to_channel(
                channel_id=channel_id, 
                message_text=message,
                user_id=mobile_user_id
            )
            
            if "error" in result:
                raise HTTPException(status_code=500, detail=result["error"])
            
            # If using real webhooks, we return immediately
            # The AI response will come via webhook and be broadcast to WebSocket
            if result.get("webhook_will_handle"):
                # Store pending message for webhook response tracking
                self._store_pending_message(channel_id, message, websocket_client_id)
                
                response_data = {
                    "status": "success",
                    "channel_id": channel_id,
                    "user_message": message,
                    "message_id": result.get("message_id"),
                    "websocket_client_id": websocket_client_id,
                    "note": "Message sent to Stream Chat. AI response will come via webhook.",
                    "webhook_flow": True
                }
                
                # Send confirmation to WebSocket client that message was received
                await self._broadcast_to_mobile_websocket(websocket_client_id, {
                    "type": "message_sent",
                    "channel_id": channel_id,
                    "user_message": message,
                    "message_id": result.get("message_id"),
                    "status": "Processing via webhook...",
                    "timestamp": asyncio.get_event_loop().time()
                })
                
            else:
                # Fallback: direct response (when Stream Chat is disabled)
                response_data = {
                    "status": "success",
                    "channel_id": channel_id,
                    "user_message": message,
                    "ai_response": result.get("ai_response"),
                    "websocket_client_id": websocket_client_id,
                    "webhook_flow": False,
                    "note": "Stream Chat disabled, used direct processing"
                }
                
                # Broadcast the response via WebSocket
                await self._broadcast_to_mobile_websocket(websocket_client_id, {
                    "type": "ai_response",
                    "channel_id": channel_id,
                    "user_message": message,
                    "ai_response": result.get("ai_response"),
                    "timestamp": asyncio.get_event_loop().time(),
                    "via_webhook": False
                })
            
            logger.info(f"Sent message to agent for channel {channel_id} via {'webhook' if result.get('webhook_will_handle') else 'direct'}")
            return response_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            # Send error via WebSocket
            try:
                websocket_client_id = self.generate_websocket_client_id(user_id, mission_id)
                await self._broadcast_to_mobile_websocket(websocket_client_id, {
                    "type": "ai_error",
                    "channel_id": self.generate_channel_id(user_id, mission_id),
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                })
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    
    def _store_pending_message(self, channel_id: str, message: str, websocket_client_id: str) -> None:
        """Store pending message waiting for webhook response"""
        self.pending_messages[channel_id] = {
            "user_message": message,
            "websocket_client_id": websocket_client_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        logger.info(f"Stored pending message for channel {channel_id}")
    
    async def handle_webhook_response(self, channel_id: str, ai_response: str) -> None:
        """Handle AI response from webhook and broadcast to mobile client"""
        try:
            if channel_id in self.pending_messages:
                pending = self.pending_messages[channel_id]
                websocket_client_id = pending["websocket_client_id"]
                
                # Broadcast the AI response via WebSocket
                await self._broadcast_to_mobile_websocket(websocket_client_id, {
                    "type": "ai_response",
                    "channel_id": channel_id,
                    "user_message": pending["user_message"],
                    "ai_response": ai_response,
                    "timestamp": asyncio.get_event_loop().time(),
                    "via_webhook": True
                })
                
                # Clean up pending message
                del self.pending_messages[channel_id]
                
                logger.info(f"Broadcasted webhook response for channel {channel_id}")
            else:
                logger.warning(f"No pending message found for channel {channel_id}")
                
        except Exception as e:
            logger.error(f"Failed to handle webhook response: {e}")

    async def send_streaming_message_to_agent(self, user_id: str, mission_id: str, message: str) -> Dict[str, Any]:
        """
        Send message to AI agent and stream response in real-time via WebSocket
        This provides ChatGPT-like streaming experience for mobile apps
        For webhook version, this works the same but processes response from webhook
        """
        try:
            channel_id = self.generate_channel_id(user_id, mission_id)
            
            # Check if channel exists
            if channel_id not in self.mobile_channels:
                raise HTTPException(status_code=404, detail="Channel not found. Please create channel first.")
            
            channel_info = self.mobile_channels[channel_id]
            websocket_client_id = channel_info["websocket_client_id"]
            
            # Send initial message to client indicating processing started
            await self._broadcast_to_mobile_websocket(websocket_client_id, {
                "type": "ai_thinking",
                "channel_id": channel_id,
                "user_message": message,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Try to use webhook flow first
            mobile_user_id = f"mobile-{user_id}"
            result = await stream_chat_manager.send_user_message_to_channel(
                channel_id=channel_id, 
                message_text=message,
                user_id=mobile_user_id
            )
            
            if result.get("webhook_will_handle"):
                # Store for streaming webhook response
                self._store_pending_streaming_message(channel_id, message, websocket_client_id)
                logger.info(f"Started webhook-based streaming for channel {channel_id}")
                
                return {
                    "status": "success",
                    "channel_id": channel_id,
                    "user_message": message,
                    "websocket_client_id": websocket_client_id,
                    "message": "Response streaming started via webhook",
                    "webhook_flow": True
                }
            else:
                # Fallback to direct streaming if webhook not available
                direct_response = result.get("ai_response")

                if direct_response:
                    # Stream the response that was already generated during direct processing
                    asyncio.create_task(
                        self._stream_response_text(direct_response, websocket_client_id, channel_id)
                    )
                    response_message = "Response streaming started (direct mode)"
                    streamed_from_cached = True
                else:
                    # As a safety net, trigger the agent directly
                    agent = self.get_or_create_mobile_agent(user_id, mission_id)
                    asyncio.create_task(
                        self._stream_agent_response(agent, message, websocket_client_id, channel_id)
                    )
                    response_message = "Response streaming started (direct mode via agent)"
                    streamed_from_cached = False
                
                return {
                    "status": "success",
                    "channel_id": channel_id,
                    "user_message": message,
                    "websocket_client_id": websocket_client_id,
                    "message": response_message,
                    "webhook_flow": False,
                    "cached_response_used": streamed_from_cached
                }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to stream message to agent: {e}")
            # Send error via WebSocket
            try:
                websocket_client_id = self.generate_websocket_client_id(user_id, mission_id)
                await self._broadcast_to_mobile_websocket(websocket_client_id, {
                    "type": "ai_error",
                    "channel_id": self.generate_channel_id(user_id, mission_id),
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                })
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to stream message: {str(e)}")
    
    def _store_pending_streaming_message(self, channel_id: str, message: str, websocket_client_id: str) -> None:
        """Store pending streaming message waiting for webhook response"""
        self.pending_messages[channel_id] = {
            "user_message": message,
            "websocket_client_id": websocket_client_id,
            "timestamp": asyncio.get_event_loop().time(),
            "streaming": True  # Mark as streaming mode
        }
        logger.info(f"Stored pending streaming message for channel {channel_id}")
    
    async def handle_webhook_streaming_response(self, channel_id: str, ai_response: str) -> None:
        """Handle AI streaming response from webhook"""
        try:
            if channel_id in self.pending_messages:
                pending = self.pending_messages[channel_id]
                websocket_client_id = pending["websocket_client_id"]
                
                if pending.get("streaming"):
                    # Stream the response word by word
                    await self._stream_response_text(ai_response, websocket_client_id, channel_id)
                else:
                    # Send as complete response
                    await self.handle_webhook_response(channel_id, ai_response)
                
                # Clean up pending message
                del self.pending_messages[channel_id]
                
            else:
                logger.warning(f"No pending message found for channel {channel_id}")
                
        except Exception as e:
            logger.error(f"Failed to handle webhook streaming response: {e}")
    
    async def _stream_response_text(self, response_text: str, websocket_client_id: str, channel_id: str) -> None:
        """Stream response text word by word to WebSocket client"""
        try:
            # Clean up the response
            clean_response = re.sub(r'\n\s*\n', '\n', response_text).strip()
            
            # Stream word by word
            words = clean_response.split()
            current_chunk = ""
            
            for i, word in enumerate(words):
                current_chunk += word
                
                # Send chunk every few words or at the end
                if i % 3 == 0 or i == len(words) - 1:
                    if current_chunk.strip():
                        await self._broadcast_to_mobile_websocket(websocket_client_id, {
                            "type": "ai_chunk",
                            "channel_id": channel_id,
                            "content": current_chunk + " ",
                            "is_final": i == len(words) - 1,
                            "timestamp": asyncio.get_event_loop().time()
                        })
                        current_chunk = ""
                        await asyncio.sleep(0.08)  # Natural feeling delay
                else:
                    current_chunk += " "
            
            # Send completion signal
            await self._broadcast_to_mobile_websocket(websocket_client_id, {
                "type": "ai_complete",
                "channel_id": channel_id,
                "timestamp": asyncio.get_event_loop().time()
            })
            
        except Exception as e:
            logger.error(f"Error streaming response text: {e}")
            await self._broadcast_to_mobile_websocket(websocket_client_id, {
                "type": "ai_error",
                "channel_id": channel_id,
                "error": f"Xin lỗi, em gặp lỗi khi stream response: {str(e)}",
                "timestamp": asyncio.get_event_loop().time()
            })

    async def _stream_agent_response(self, agent: Any, message: str, websocket_client_id: str, channel_id: str) -> None:
        """Stream agent response in real-time to WebSocket client (fallback method)"""
        try:
            # Use direct agent.run to get clean response without borders/formatting
            response = agent.run(message)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response (remove any potential formatting artifacts)
            clean_response = content.strip()
            
            # Stream the content word by word
            await self._stream_response_text(clean_response, websocket_client_id, channel_id)
            
        except Exception as e:
            logger.error(f"Error streaming agent response: {e}")
            # Send error via WebSocket
            await self._broadcast_to_mobile_websocket(websocket_client_id, {
                "type": "ai_error",
                "channel_id": channel_id,
                "error": f"Xin lỗi, em gặp lỗi khi xử lý yêu cầu: {str(e)}",
                "timestamp": asyncio.get_event_loop().time()
            })
    
    async def _broadcast_to_mobile_websocket(self, websocket_client_id: str, message: Dict[str, Any]) -> None:
        """Broadcast message to mobile WebSocket client"""
        try:
            await websocket_manager.send_personal_message(message, websocket_client_id)
        except Exception as e:
            logger.warning(f"Failed to broadcast to WebSocket client {websocket_client_id}: {e}")
    
    def get_user_channels(self, user_id: str) -> Dict[str, Any]:
        """Get all channels for a user"""
        user_channels = {}
        
        if user_id in self.user_sessions:
            for mission_id, channel_id in self.user_sessions[user_id].items():
                if channel_id in self.mobile_channels:
                    channel_info = self.mobile_channels[channel_id]
                    user_channels[mission_id] = {
                        "channel_id": channel_id,
                        "websocket_client_id": channel_info["websocket_client_id"],
                        "created_at": channel_info["created_at"],
                        "webhook_enabled": channel_info.get("webhook_enabled", True)
                    }
        
        return user_channels
    
    async def close_mobile_channel(self, user_id: str, mission_id: str) -> Dict[str, Any]:
        """Close mobile channel and stop AI agent"""
        try:
            channel_id = self.generate_channel_id(user_id, mission_id)
            
            if channel_id not in self.mobile_channels:
                return {"status": "not_found", "message": "Channel not found"}
            
            # Stop AI agent
            await stream_chat_manager.stop_agent(channel_id)
            
            # Remove from tracking
            del self.mobile_channels[channel_id]
            
            if user_id in self.user_sessions and mission_id in self.user_sessions[user_id]:
                del self.user_sessions[user_id][mission_id]
                
                # Clean up empty user session
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]
            
            # Clean up mobile agent
            agent_key = f"{user_id}_{mission_id}"
            if agent_key in self.active_mobile_agents:
                del self.active_mobile_agents[agent_key]
            
            # Clean up any pending messages
            if channel_id in self.pending_messages:
                del self.pending_messages[channel_id]
            
            logger.info(f"Closed mobile channel {channel_id}")
            
            return {
                "status": "success",
                "channel_id": channel_id,
                "message": "Channel closed successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to close mobile channel: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to close channel: {str(e)}")
    
    def get_channel_info(self, user_id: str, mission_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific channel"""
        channel_id = self.generate_channel_id(user_id, mission_id)
        
        if channel_id in self.mobile_channels:
            return {
                "channel_id": channel_id,
                **self.mobile_channels[channel_id]
            }
        
        return None

# Global webhook-based mobile channel manager
webhook_mobile_channel_manager = WebhookMobileChannelManager()

# API endpoint functions with TRUE WEBHOOK SUPPORT
async def create_mobile_channel_webhook_api(request: MobileChannelRequest) -> Dict[str, Any]:
    """API endpoint to create mobile channel with webhook support"""
    return await webhook_mobile_channel_manager.create_mobile_channel(
        user_id=request.user_id,
        mission_id=request.mission_id
    )

async def send_mobile_message_webhook_api(request: MobileChatMessage) -> Dict[str, Any]:
    """API endpoint to send message to AI agent via webhook"""
    return await webhook_mobile_channel_manager.send_message_to_agent(
        user_id=request.user_id,
        mission_id=request.mission_id,
        message=request.message
    )

async def send_mobile_stream_message_webhook_api(request: MobileStreamMessage) -> Dict[str, Any]:
    """API endpoint to send message to AI agent with webhook-based streaming response"""
    return await webhook_mobile_channel_manager.send_streaming_message_to_agent(
        user_id=request.user_id,
        mission_id=request.mission_id,
        message=request.message
    )

async def get_user_channels_webhook_api(user_id: str) -> Dict[str, Any]:
    """API endpoint to get user's channels"""
    channels = webhook_mobile_channel_manager.get_user_channels(user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "channels": channels,
        "count": len(channels),
        "webhook_enabled": True
    }

async def close_mobile_channel_webhook_api(request: MobileChannelRequest) -> Dict[str, Any]:
    """API endpoint to close mobile channel"""
    return await webhook_mobile_channel_manager.close_mobile_channel(
        user_id=request.user_id,
        mission_id=request.mission_id
    )

async def get_channel_info_webhook_api(user_id: str, mission_id: str) -> Dict[str, Any]:
    """API endpoint to get channel information"""
    channel_info = webhook_mobile_channel_manager.get_channel_info(user_id, mission_id)
    
    if channel_info:
        return {
            "status": "success",
            "channel_info": channel_info
        }
    else:
        raise HTTPException(status_code=404, detail="Channel not found")

# Function to handle webhook responses (called from webhook endpoint)
async def handle_webhook_ai_response(channel_id: str, ai_response: str, streaming: bool = False) -> None:
    """Handle AI response from webhook and broadcast to mobile clients"""
    if streaming:
        await webhook_mobile_channel_manager.handle_webhook_streaming_response(channel_id, ai_response)
    else:
        await webhook_mobile_channel_manager.handle_webhook_response(channel_id, ai_response)
