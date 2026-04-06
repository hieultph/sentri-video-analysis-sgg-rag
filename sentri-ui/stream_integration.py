"""
Stream Chat integration for Agno AI Agent
This module provides Stream Chat integration for the irrigation assistant
"""
import os
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from stream_chat import StreamChat
from agents.assistant import get_assistant_agent
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class StreamChatConfig:
    """Configuration for Stream Chat"""
    
    def __init__(self):
        self.api_key = os.getenv('4cs287ukv3zd')
        self.api_secret = os.getenv('6vtk3g9kgyd9xjgvdbyfmss8asc28pgna39v9qwrwbn952rc5cc6frs7q3pjvkzy')
        self.enabled = bool(self.api_key and self.api_secret)
        
        if not self.enabled:
            logger.warning(
                "Stream Chat credentials not found. "
                "Stream Chat integration will be disabled. "
                "Add STREAM_API_KEY and STREAM_API_SECRET to .env to enable."
            )
    
    def get_server_client(self) -> Optional[StreamChat]:
        """Get Stream Chat server client"""
        if not self.enabled:
            return None
        return StreamChat(self.api_key, self.api_secret)

class AgnoStreamAgent:
    """
    Wrapper class that integrates Agno AI Agent with Stream Chat
    """
    
    def __init__(self, user_id: str, channel_type: str, channel_id: str):
        self.user_id = user_id
        self.channel_type = channel_type
        self.channel_id = channel_id
        self.last_interaction = asyncio.get_event_loop().time()
        
        # Initialize Stream Chat
        self.config = StreamChatConfig()
        self.server_client = self.config.get_server_client()
        self.client_connection = None
        self.channel = None
        
        # Check if Stream Chat is available
        self.stream_chat_enabled = self.config.enabled
        
        # Initialize Agno Agent
        self.agno_agent = get_assistant_agent(user_id)
        
        if self.stream_chat_enabled:
            logger.info(f"Created AgnoStreamAgent for user {user_id} in channel {channel_id}")
        else:
            logger.info(f"Created AgnoStreamAgent for user {user_id} (Stream Chat disabled)")
    
    async def init(self) -> None:
        """Initialize the agent and connect to Stream Chat"""
        try:
            if not self.stream_chat_enabled:
                logger.info(f"Agent {self.user_id} initialized (Stream Chat disabled)")
                return
            
            # Create user token
            token = self.server_client.create_token(self.user_id)
            
            # Connect user to Stream Chat
            user_data = {
                'id': self.user_id,
                'name': 'Trợ lý Tưới tiêu AI',
                'role': 'admin',
                'image': '🤖'
            }
            
            # Update user in Stream
            await asyncio.to_thread(self.server_client.upsert_user, user_data)
            
            # Get channel and join
            self.channel = self.server_client.channel(self.channel_type, self.channel_id)
            
            # Add AI bot to channel
            try:
                await asyncio.to_thread(self.channel.add_members, [self.user_id])
            except Exception as e:
                logger.warning(f"Failed to add user to channel: {e}")
            
            # Watch channel (if available)
            try:
                # Try different methods to watch/query the channel
                if hasattr(self.channel, 'watch'):
                    await asyncio.to_thread(self.channel.watch)
                elif hasattr(self.channel, 'query'):
                    await asyncio.to_thread(self.channel.query)
                else:
                    logger.info(f"Channel watching not available for {self.channel_id}")
            except Exception as e:
                logger.warning(f"Failed to watch channel: {e} - continuing without channel watching")
            
            logger.info(f"Agent {self.user_id} initialized and connected to channel {self.channel_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
    
    async def handle_message(self, message_data: Dict[str, Any]) -> None:
        """Handle incoming webhook message and stream response to mobile clients"""
        try:
            message_text = message_data.get("message", {}).get("text", "")
            channel_id = message_data.get("channel_id", "")
            
            # Skip if empty message
            if not message_text:
                return
            
            # Skip AI generated messages to avoid loops
            if message_data.get("message", {}).get("ai_generated", False):
                logger.info("Skipping AI generated message")
                return
            
            self.last_interaction = asyncio.get_event_loop().time()
            logger.info(f"Processing message: {message_text}")
            
            # Get response from Agno agent using clean run() method
            try:
                # Run Agno agent in thread to avoid blocking
                agno_response = await asyncio.to_thread(
                    self.agno_agent.run, 
                    message_text
                )
                
                # Extract response content cleanly
                response_content = agno_response.content if hasattr(agno_response, 'content') else str(agno_response)
                response_content = response_content.strip()  # Remove any extra whitespace
                
                # Send response to Stream Chat
                await self.send_message(response_content)
                
                # WEBHOOK INTEGRATION: Also notify mobile clients
                await self._notify_mobile_webhook_response(response_content)
                
                logger.info(f"Sent response to channel: {response_content[:100]}...")
                
            except Exception as e:
                logger.error(f"Error getting Agno response: {e}")
                error_message = "Xin lỗi, em gặp lỗi khi xử lý yêu cầu của anh/chị. Vui lòng thử lại."
                await self.send_message(error_message)
                await self._notify_mobile_webhook_response(error_message)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def send_message(self, text: str) -> Dict[str, Any]:
        """Send message to Stream Chat channel"""
        try:
            if not self.stream_chat_enabled or not self.channel:
                logger.info(f"Would send message (Stream Chat disabled): {text[:100]}...")
                return {"message": {"text": text}, "simulated": True}
            
            message_data = {
                'text': text,
                'ai_generated': True,
                'user_id': self.user_id
            }
            
            response = await asyncio.to_thread(
                self.channel.send_message,
                message_data
            )
            
            logger.info(response)
            return response
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def send_ai_indicator(self, state: str, message_id: Optional[str] = None) -> None:
        """Send AI indicator event to Stream Chat"""
        try:
            if not self.stream_chat_enabled or not self.channel:
                logger.debug(f"Would send AI indicator (Stream Chat disabled): {state}")
                return
            
            event_data = {
                'type': 'ai_indicator.update',
                'ai_state': state
            }
            
            if message_id:
                event_data['message_id'] = message_id
            
            if state == 'AI_STATE_CLEAR':
                event_data['type'] = 'ai_indicator.clear'
            
            await asyncio.to_thread(self.channel.send_event, event_data)
            
        except Exception as e:
            logger.warning(f"Failed to send AI indicator: {e}")
    
    async def dispose(self) -> None:
        """Clean up agent resources"""
        try:
            if self.stream_chat_enabled and self.channel:
                # Remove user from channel
                await asyncio.to_thread(self.channel.remove_members, [self.user_id])
            
            logger.info(f"Agent {self.user_id} disposed")
            
        except Exception as e:
            logger.error(f"Error disposing agent: {e}")
    
    def get_last_interaction(self) -> float:
        """Get last interaction timestamp"""
        return self.last_interaction
    
    def get_session_state(self) -> Dict[str, Any]:
        """Get current agent session state"""
        return self.agno_agent.session_state if hasattr(self.agno_agent, 'session_state') else {}
    
    async def send_test_message(self, message_text: str) -> str:
        """Send a message directly to the agent for testing (when Stream Chat is disabled)"""
        try:
            self.last_interaction = asyncio.get_event_loop().time()
            
            # Get response from Agno agent
            agno_response = await asyncio.to_thread(
                self.agno_agent.run, 
                message_text
            )
            
            # Extract response content
            response_content = agno_response.content if hasattr(agno_response, 'content') else str(agno_response)
            
            logger.info(f"Agent {self.user_id} processed message: {message_text[:50]}...")

            print(f"Agent response: {response_content[:50]}...")
            return response_content
            
        except Exception as e:
            logger.error(f"Error processing test message: {e}")
            return f"Xin lỗi, em gặp lỗi khi xử lý yêu cầu: {str(e)}"
    
    async def _notify_mobile_webhook_response(self, ai_response: str) -> None:
        """Notify mobile clients of AI response via webhook handler"""
        try:
            # Extract channel_id from user_id
            if self.user_id.startswith("ai-irrigation-"):
                # Convert back to mobile channel format
                channel_part = self.user_id.replace("ai-irrigation-", "")
                channel_id = channel_part.replace("-", "-", 2)  # First two dashes become channel format
                
                # Import here to avoid circular imports
                try:
                    from mobile_api_webhook import handle_webhook_ai_response
                    await handle_webhook_ai_response(channel_id, ai_response, streaming=False)
                    logger.info(f"Notified mobile webhook handler for channel {channel_id}")
                except ImportError:
                    logger.warning("mobile_api_webhook not available - webhook notification skipped")
                except Exception as e:
                    logger.error(f"Failed to notify mobile webhook handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error in mobile webhook notification: {e}")

class StreamChatManager:
    """
    Manager for Stream Chat agents
    """
    
    def __init__(self):
        self.agents: Dict[str, AgnoStreamAgent] = {}
        self.config = StreamChatConfig()
        self.cleanup_interval = 300  # 5 minutes
        self.inactivity_threshold = 1800  # 30 minutes
        self._cleanup_task = None
        self._initialized = False
        self.stream_chat_enabled = self.config.enabled
    
    async def _ensure_initialized(self):
        """Ensure manager is initialized with async components"""
        if not self._initialized:
            try:
                # Start cleanup task if not already running
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self._cleanup_inactive_agents())
                self._initialized = True
                logger.info("StreamChatManager initialized")
            except Exception as e:
                logger.error(f"Failed to initialize StreamChatManager: {e}")
    
    async def start_agent(self, channel_id: str, channel_type: str = 'messaging') -> Dict[str, Any]:
        """Start AI agent for a channel"""
        try:
            # Ensure manager is initialized
            await self._ensure_initialized()
            
            # Generate unique user ID for this channel
            user_id = f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
            
            # Check if agent already exists
            if user_id in self.agents:
                logger.info(f"Agent {user_id} already exists")
                return {"status": "already_running", "user_id": user_id}
            
            # Create and initialize agent
            agent = AgnoStreamAgent(user_id, channel_type, channel_id)
            await agent.init()
            
            # Store agent
            self.agents[user_id] = agent
            
            logger.info(f"Started agent {user_id} for channel {channel_id}")
            
            return {
                "status": "started",
                "user_id": user_id,
                "channel_id": channel_id,
                "message": "AI Agent started successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to start agent: {e}")
            raise
    
    async def stop_agent(self, channel_id: str) -> Dict[str, Any]:
        """Stop AI agent for a channel"""
        try:
            # Ensure manager is initialized
            await self._ensure_initialized()
            
            user_id = f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
            
            if user_id in self.agents:
                agent = self.agents[user_id]
                await agent.dispose()
                del self.agents[user_id]
                
                logger.info(f"Stopped agent {user_id}")
                return {"status": "stopped", "user_id": user_id}
            else:
                return {"status": "not_found", "message": "Agent not found"}
                
        except Exception as e:
            logger.error(f"Failed to stop agent: {e}")
            raise
    
    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> None:
        """Handle Stream Chat webhook events"""
        try:
            # Ensure manager is initialized
            await self._ensure_initialized()
            
            event_type = webhook_data.get('type')
            
            if event_type == 'message.new':
                await self._handle_new_message(webhook_data)
            elif event_type == 'ai_indicator.stop':
                await self._handle_stop_generation(webhook_data)
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
    
    async def _handle_new_message(self, webhook_data: Dict[str, Any]) -> None:
        """Handle new message webhook"""
        try:
            channel_id = webhook_data.get('channel_id')
            message = webhook_data.get('message', {})
            
            if not channel_id or not message:
                return
            
            # Find agent for this channel
            user_id = f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
            
            if user_id in self.agents:
                agent = self.agents[user_id]
                await agent.handle_message(message)
            
        except Exception as e:
            logger.error(f"Error handling new message: {e}")
    
    async def _handle_stop_generation(self, webhook_data: Dict[str, Any]) -> None:
        """Handle stop generation request"""
        try:
            channel_id = webhook_data.get('channel_id')
            user_id = f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
            
            if user_id in self.agents:
                agent = self.agents[user_id]
                await agent.send_ai_indicator('AI_STATE_CLEAR')
                logger.info(f"Stopped generation for agent {user_id}")
            
        except Exception as e:
            logger.error(f"Error stopping generation: {e}")
    
    async def _cleanup_inactive_agents(self) -> None:
        """Cleanup inactive agents periodically"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                current_time = asyncio.get_event_loop().time()
                inactive_agents = []
                
                for user_id, agent in self.agents.items():
                    if current_time - agent.get_last_interaction() > self.inactivity_threshold:
                        inactive_agents.append(user_id)
                
                # Remove inactive agents
                for user_id in inactive_agents:
                    logger.info(f"Removing inactive agent {user_id}")
                    agent = self.agents[user_id]
                    await agent.dispose()
                    del self.agents[user_id]
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    def get_active_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active agents"""
        return {
            user_id: {
                "user_id": agent.user_id,
                "channel_id": agent.channel_id,
                "channel_type": agent.channel_type,
                "last_interaction": agent.get_last_interaction(),
                "session_state": agent.get_session_state()
            }
            for user_id, agent in self.agents.items()
        }
    
    async def send_test_message(self, channel_id: str, message_text: str) -> Dict[str, Any]:
        """Send a test message to an agent (useful when Stream Chat is disabled)"""
        try:
            await self._ensure_initialized()
            
            user_id = f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
            
            if user_id not in self.agents:
                return {"error": "Agent not found", "message": "Please start the agent first"}
            
            agent = self.agents[user_id]
            response = await agent.send_test_message(message_text)
            
            return {
                "status": "success",
                "channel_id": channel_id,
                "user_message": message_text,
                "ai_response": response
            }
            
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")
            return {"error": str(e)}
    
    async def send_user_message_to_channel(self, channel_id: str, message_text: str, user_id: str = "mobile_user") -> Dict[str, Any]:
        """Send a user message to Stream Chat channel (will trigger webhook)"""
        try:
            await self._ensure_initialized()
            
            # Get the agent for this channel
            agent_user_id = f"ai-irrigation-{channel_id.replace('!', '').replace(':', '-')}"
            
            if agent_user_id not in self.agents:
                return {"error": "Agent not found", "message": "Please start the agent first"}
            
            agent = self.agents[agent_user_id]
            
            # Send message as user to the Stream Chat channel
            if self.stream_chat_enabled and agent.channel:
                try:
                    # Send user message to Stream Chat
                    message_data = {
                        'text': message_text,
                        'user_id': user_id,  # This represents the mobile user
                        'ai_generated': False
                    }
                    
                    # Send to Stream Chat - this will trigger webhook back to our server
                    response = await asyncio.to_thread(
                        agent.channel.send_message,
                        message_data
                    )
                    
                    return {
                        "status": "success",
                        "channel_id": channel_id,
                        "message_sent": True,
                        "message_id": response.get('message', {}).get('id'),
                        "webhook_will_handle": True,
                        "note": "AI response will come via webhook"
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to send to Stream Chat, falling back to direct: {e}")
                    # Fallback to direct processing if Stream Chat fails
                    return await self.send_test_message(channel_id, message_text)
            else:
                # Stream Chat disabled, process directly
                logger.info("Stream Chat disabled, processing message directly")
                return await self.send_test_message(channel_id, message_text)
            
        except Exception as e:
            logger.error(f"Failed to send user message to channel: {e}")
            return {"error": str(e)}

# Global manager instance
stream_chat_manager = StreamChatManager()
