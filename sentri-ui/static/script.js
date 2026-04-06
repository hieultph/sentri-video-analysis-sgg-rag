// Sentri Dashboard JavaScript

// Global state
let currentUser = null;
let cameras = [];
let selectedCameraId = null;
let chatHistory = [];
let currentEvents = []; // Store current loaded events

// Auth helpers
function getAuthToken() {
  return localStorage.getItem("sentri_token");
}

function getAuthHeaders() {
  const token = getAuthToken();
  return {
    "Content-Type": "application/json",
    Authorization: token ? `Bearer ${token}` : "",
  };
}

function logout() {
  localStorage.removeItem("sentri_token");
  localStorage.removeItem("sentri_user");
  window.location.href = "/static/login.html";
}

// Check authentication on page load
async function checkAuth() {
  const token = getAuthToken();
  if (!token) {
    window.location.href = "/static/login.html";
    return false;
  }

  try {
    const response = await fetch("/auth/me", {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      logout();
      return false;
    }

    currentUser = await response.json();
    document.getElementById(
      "userInfo"
    ).textContent = `Logged in as ${currentUser.username}`;
    return true;
  } catch (error) {
    console.error("Auth check failed:", error);
    logout();
    return false;
  }
}

// Load cameras
async function loadCameras() {
  try {
    const response = await fetch("/camera/list", {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error("Failed to load cameras");
    }

    const data = await response.json();
    cameras = data.cameras;

    // Update camera dropdown
    const select = document.getElementById("cameraSelect");
    select.innerHTML = '<option value="">Select a camera...</option>';

    cameras.forEach((camera) => {
      const option = document.createElement("option");
      option.value = camera.id;
      option.textContent = `${camera.name}${
        camera.location ? " (" + camera.location + ")" : ""
      }`;
      select.appendChild(option);
    });

    // Auto-select first camera if available
    if (cameras.length > 0 && !selectedCameraId) {
      select.value = cameras[0].id;
      onCameraChange();
    } else if (cameras.length === 0) {
      // Hide buttons when no cameras
      document.getElementById("deleteCameraBtn").style.display = "none";
      document.getElementById("clearHistoryBtn").style.display = "none";
    }
  } catch (error) {
    console.error("Failed to load cameras:", error);
  }
}

// Camera selection change
function onCameraChange() {
  const select = document.getElementById("cameraSelect");
  const deleteBtn = document.getElementById("deleteCameraBtn");
  const clearHistoryBtn = document.getElementById("clearHistoryBtn");
  selectedCameraId = select.value ? parseInt(select.value) : null;

  if (selectedCameraId) {
    const camera = cameras.find((c) => c.id === selectedCameraId);
    if (camera) {
      updateVideoStream(camera);
      loadCameraConfig(selectedCameraId);
      loadEvents();
      deleteBtn.style.display = "inline-block"; // Show delete button
      clearHistoryBtn.style.display = "inline-block"; // Show clear history button
    }
  } else {
    clearVideoStream();
    deleteBtn.style.display = "none"; // Hide delete button
    clearHistoryBtn.style.display = "none"; // Hide clear history button
  }
}

// Update video stream display
function updateVideoStream(camera) {
  const container = document.getElementById("videoContainer");
  const statusBadge = document.getElementById("videoStatus");

  // Clear previous content
  container.innerHTML = "";

  // Show loading state
  statusBadge.textContent = `Connecting to ${camera.name}...`;
  statusBadge.className = "status-badge";

  const streamUrl = camera.stream_url;

  // Always try to display as image stream first (works for MJPEG, webcam streams)
  // Most IP cameras and webcam streams use MJPEG format via HTTP
  const img = document.createElement("img");
  img.id = "liveImage";
  img.src = streamUrl;
  img.alt = "Live camera stream";
  img.style.width = "100%";
  img.style.height = "auto";
  img.style.display = "block";
  img.style.maxHeight = "600px";
  img.style.objectFit = "contain";

  img.onload = () => {
    statusBadge.textContent = `✓ Streaming: ${camera.name}`;
    statusBadge.className = "status-badge active";
    console.log("Stream connected successfully:", streamUrl);
  };

  img.onerror = () => {
    console.error("Failed to load stream:", streamUrl);
    // If image fails, try video element for other formats (HLS, MP4, etc.)
    tryVideoStream(container, camera, statusBadge);
  };

  container.appendChild(img);
}

// Try video element if image stream fails
function tryVideoStream(container, camera, statusBadge) {
  container.innerHTML = "";

  const video = document.createElement("video");
  video.id = "liveVideo";
  video.autoplay = true;
  video.muted = true;
  video.controls = true;
  video.style.width = "100%";
  video.style.maxHeight = "600px";

  const source = document.createElement("source");
  source.src = camera.stream_url;
  source.type = "application/x-mpegURL"; // For HLS

  video.appendChild(source);

  video.onloadeddata = () => {
    statusBadge.textContent = `✓ Streaming: ${camera.name}`;
    statusBadge.className = "status-badge active";
    console.log("Video stream connected:", camera.stream_url);
  };

  video.onerror = () => {
    console.error(
      "Both image and video streams failed for:",
      camera.stream_url
    );
    showStreamError(container, camera.stream_url);
    statusBadge.textContent = "✗ Stream unavailable";
    statusBadge.className = "status-badge";
  };

  container.appendChild(video);
}

function showStreamError(container, streamUrl) {
  container.innerHTML = `
        <div class="video-placeholder">
            <p style="font-size: 1.3rem; margin-bottom: 15px;">⚠️ Unable to load stream</p>
            <p style="font-size: 0.9rem; margin-bottom: 10px; color: var(--text-muted);">
                Stream URL: <code style="background: var(--bg-dark); padding: 4px 8px; border-radius: 4px;">${streamUrl}</code>
            </p>
            <p style="font-size: 0.85rem; margin: 15px 0; color: var(--text-muted);">
                Possible causes:<br>
                • Camera is offline or URL is incorrect<br>
                • Network connectivity issues<br>
                • CORS restrictions (try opening in new tab)
            </p>
            <div style="display: flex; gap: 10px; justify-content: center; margin-top: 20px;">
                <button onclick="window.open('${streamUrl}', '_blank')" 
                        class="btn btn-primary">
                    🔗 Open Stream in New Tab
                </button>
                <button onclick="location.reload()" 
                        class="btn btn-secondary">
                    🔄 Reload Page
                </button>
            </div>
        </div>
    `;
}

function clearVideoStream() {
  const container = document.getElementById("videoContainer");
  const statusBadge = document.getElementById("videoStatus");

  container.innerHTML =
    '<div class="video-placeholder"><p>Select a camera to view stream</p></div>';
  statusBadge.textContent = "No camera selected";
  statusBadge.className = "status-badge";
}

// Load events
async function loadEvents() {
  try {
    const cameraId = selectedCameraId || "";
    const eventName = document.getElementById("eventFilter").value;

    const params = new URLSearchParams();
    if (cameraId) params.append("camera_id", cameraId);
    if (eventName) params.append("event_name", eventName);

    const response = await fetch(`/events?${params}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error("Failed to load events");
    }

    const data = await response.json();
    currentEvents = data.events; // Store events globally
    displayEvents(currentEvents);
  } catch (error) {
    console.error("Failed to load events:", error);
  }
}

// Display events in table
function displayEvents(events) {
  const tbody = document.getElementById("eventsTableBody");
  const countBadge = document.getElementById("eventCount");

  countBadge.textContent = `${events.length} events`;

  if (events.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" class="no-data">No events found</td></tr>';
    return;
  }

  tbody.innerHTML = events
    .map(
      (event) => `
        <tr>
            <td>${formatDateTime(event.occurred_at)}</td>
            <td>${event.camera_name}</td>
            <td>${formatEventName(event.event_name)}</td>
            <td><span class="severity-badge severity-${event.severity}">Level ${
        event.severity
      }</span></td>
            <td>${
              event.confidence
                ? (event.confidence * 100).toFixed(1) + "%"
                : "N/A"
            }</td>
            <td>
                <button class="action-btn" onclick="viewEventDetails(${
                  event.id
                })">
                    View
                </button>
            </td>
            <td>
                <button class="action-btn scene-btn" onclick="showSceneGraph(${
                  event.id
                })">
                    Scene Graph
                </button>
            </td>
        </tr>
    `
    )
    .join("");
}

function viewEventDetails(eventId) {
  const event = currentEvents.find((e) => e.id === eventId);
  if (event) {
    showEventDetailsModal(event);
  } else {
    alert("Event details not found.");
  }
}

// Show event details modal
function showEventDetailsModal(event) {
  const modal = document.getElementById("eventDetailsModal");
  const content = document.getElementById("eventDetailsContent");

  // Show loading state
  content.innerHTML = '<div class="loading">Loading event details...</div>';
  modal.style.display = "flex";

  // Build the event details HTML
  const timestamp = new Date(event.occurred_at).toLocaleString();
  const severity_label = getSeverityLabel(event.severity);
  const confidenceText = event.confidence
    ? (event.confidence * 100).toFixed(1) + "%"
    : "N/A";

  let frameHtml = "";
  if (event.file_path) {
    // Use file_path directly as it already includes "static/recordings/frames/"
    const frameUrl = `/${event.file_path}`;
    frameHtml = `
      <div class="event-frame-container">
        <h4>📸 Captured Frame</h4>
        <img src="${frameUrl}" alt="Event Frame" class="event-frame-image" 
             onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
        <div style="display: none; color: var(--text-muted); margin-top: 10px;">
          Frame image not available
        </div>
        <p><small>Captured at: ${timestamp}</small></p>
      </div>
    `;
  } else {
    frameHtml = `
      <div class="event-frame-container">
        <h4>📸 Event Frame</h4>
        <div style="color: var(--text-muted); padding: 20px;">
          No frame captured for this event
        </div>
      </div>
    `;
  }

  content.innerHTML = `
    ${frameHtml}
    <div class="event-info-grid">
      <div class="event-info-card">
        <div class="event-info-label">Event Type</div>
        <div class="event-info-value">${event.event_name}</div>
      </div>
      <div class="event-info-card">
        <div class="event-info-label">Camera</div>
        <div class="event-info-value">${event.camera_name}</div>
      </div>
      <div class="event-info-card">
        <div class="event-info-label">Severity</div>
        <div class="event-info-value">${severity_label}</div>
      </div>
      <div class="event-info-card">
        <div class="event-info-label">Confidence</div>
        <div class="event-info-value">${confidenceText}</div>
      </div>
      <div class="event-info-card">
        <div class="event-info-label">Time</div>
        <div class="event-info-value">${timestamp}</div>
      </div>
      <div class="event-info-card">
        <div class="event-info-label">Description</div>
        <div class="event-info-value">${
          event.description || "No description available"
        }</div>
      </div>
    </div>
  `;
}

function closeEventDetailsModal() {
  document.getElementById("eventDetailsModal").style.display = "none";
}

// Helper function to get severity label
function getSeverityLabel(severity) {
  const labels = {
    1: "Level 1 (Low)",
    2: "Level 2 (Low-Medium)",
    3: "Level 3 (Medium)",
    4: "Level 4 (Medium-High)",
    5: "Level 5 (High)",
  };
  return labels[severity] || `Level ${severity}`;
}

// Show scene graph modal
function showSceneGraph(eventId) {
  const event = currentEvents.find((e) => e.id === eventId);
  if (!event) {
    alert("Event not found.");
    return;
  }

  const modal = document.getElementById("sceneGraphModal");
  const content = document.getElementById("sceneGraphContent");

  // Show modal
  modal.style.display = "flex";

  // Display scene graph data
  const graph = event.graph_json;
  if (!graph) {
    content.innerHTML =
      '<div class="error">No scene graph data available.</div>';
    return;
  }

  let html = `
    <div class="scene-graph-header">
      <h4>Event: ${formatEventName(event.event_name)}</h4>
      <p><strong>Camera:</strong> ${event.camera_name}</p>
      <p><strong>Time:</strong> ${formatDateTime(event.occurred_at)}</p>
      <p><strong>Confidence:</strong> ${
        event.confidence ? (event.confidence * 100).toFixed(1) + "%" : "N/A"
      }</p>
    </div>
    
    <div class="scene-graph-data">
  `;

  // Display objects
  if (graph.objects && graph.objects.length > 0) {
    html += `
      <div class="objects-section">
        <h5>🎯 Detected Objects (${
          graph.num_objects || graph.objects.length
        })</h5>
        <div class="objects-grid">
    `;

    graph.objects.forEach((obj) => {
      html += `
        <div class="object-card">
          <div class="object-label">${obj.label}</div>
          <div class="object-confidence">Confidence: ${(
            obj.confidence * 100
          ).toFixed(1)}%</div>
          <div class="object-coords">
            Position: (${obj.x1}, ${obj.y1}) to (${obj.x2}, ${obj.y2})
          </div>
          <div class="object-id">ID: ${obj.object_id}</div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
  }

  // Display relationships
  if (graph.relationships && graph.relationships.length > 0) {
    html += `
      <div class="relationships-section">
        <h5>🔗 Relationships (${
          graph.num_relationships || graph.relationships.length
        })</h5>
        <div class="relationships-list">
    `;

    graph.relationships.forEach((rel) => {
      const subjectObj = graph.objects.find(
        (o) => o.object_id === rel.subject_id
      );
      const objectObj = graph.objects.find(
        (o) => o.object_id === rel.object_id
      );

      html += `
        <div class="relationship-card">
          <div class="relationship-text">
            <span class="subject">${
              subjectObj ? subjectObj.label : "Object " + rel.subject_id
            }</span>
            <span class="predicate">${rel.predicate}</span>
            <span class="object">${
              objectObj ? objectObj.label : "Object " + rel.object_id
            }</span>
          </div>
          <div class="relationship-confidence">
            Confidence: ${(rel.confidence * 100).toFixed(1)}%
          </div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
  }

  // Raw JSON section (collapsible)
  html += `
    <div class="raw-json-section">
      <h5 onclick="toggleRawJson()" class="toggle-header">📄 Raw JSON Data <span class="toggle-icon">▼</span></h5>
      <pre id="rawJsonContent" class="raw-json" style="display: none;">${JSON.stringify(
        graph,
        null,
        2
      )}</pre>
    </div>
  `;

  html += `</div>`;

  content.innerHTML = html;
}

// Close scene graph modal
function closeSceneGraphModal() {
  document.getElementById("sceneGraphModal").style.display = "none";
}

// Toggle raw JSON display
function toggleRawJson() {
  const content = document.getElementById("rawJsonContent");
  const icon = document.querySelector(".toggle-icon");

  if (content.style.display === "none") {
    content.style.display = "block";
    icon.textContent = "▲";
  } else {
    content.style.display = "none";
    icon.textContent = "▼";
  }
}

// Load notifications
async function loadNotifications() {
  try {
    const response = await fetch("/notifications", {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error("Failed to load notifications");
    }

    const data = await response.json();
    displayNotifications(data.notifications);
  } catch (error) {
    console.error("Failed to load notifications:", error);
  }
}

// Display notifications
function displayNotifications(notifications) {
  const container = document.getElementById("notificationsList");
  const unreadCount = document.getElementById("unreadCount");

  const unread = notifications.filter((n) => !n.is_read).length;
  unreadCount.textContent = `${unread} unread`;

  if (notifications.length === 0) {
    container.innerHTML = '<p class="no-data">No notifications</p>';
    return;
  }

  container.innerHTML = notifications
    .map(
      (notif) => `
        <div class="notification-item ${notif.is_read ? "" : "unread"}" 
             onclick="markNotificationRead(${notif.id})">
            <div class="notification-header">
                <span class="notification-title">${notif.title}</span>
                <span class="notification-time">${formatDateTime(
                  notif.created_at
                )}</span>
            </div>
            <div class="notification-message">${notif.message}</div>
        </div>
    `
    )
    .join("");
}

// Mark notification as read
async function markNotificationRead(notificationId) {
  try {
    const response = await fetch(`/notifications/${notificationId}/read`, {
      method: "POST",
      headers: getAuthHeaders(),
    });

    if (response.ok) {
      loadNotifications(); // Reload notifications
    }
  } catch (error) {
    console.error("Failed to mark notification as read:", error);
  }
}

// Add camera modal
function openAddCameraModal() {
  document.getElementById("addCameraModal").classList.add("active");
}

function closeAddCameraModal() {
  document.getElementById("addCameraModal").classList.remove("active");
  document.getElementById("addCameraForm").reset();
}

document
  .getElementById("addCameraForm")
  .addEventListener("submit", async (e) => {
    e.preventDefault();

    const name = document.getElementById("cameraName").value;
    const location = document.getElementById("cameraLocation").value;
    const stream_url = document.getElementById("streamUrl").value;

    try {
      const response = await fetch("/camera/add", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ name, location, stream_url }),
      });

      if (!response.ok) {
        const data = await response.json();
        alert("Failed to add camera: " + (data.detail || "Unknown error"));
        return;
      }

      alert("Camera added successfully!");
      closeAddCameraModal();
      loadCameras(); // Reload cameras
    } catch (error) {
      console.error("Failed to add camera:", error);
      alert("Network error. Please try again.");
    }
  });

// Chat modal
function openChatModal() {
  document.getElementById("chatModal").classList.add("active");
  document.getElementById("chatInput").focus();
}

function closeChatModal() {
  document.getElementById("chatModal").classList.remove("active");
}

function handleChatKeyPress(event) {
  if (event.key === "Enter") {
    sendChatMessage();
  }
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();

  if (!message) return;

  // Add user message to history
  addChatMessage("user", message);
  input.value = "";

  // Show typing indicator
  const typingId = addChatMessage("agent", "Sentri is thinking...");

  try {
    const response = await fetch("/agent/chat", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        message: message,
        camera_id: selectedCameraId,
        filters: {},
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to get response");
    }

    const data = await response.json();

    // Remove typing indicator
    document.getElementById(typingId).remove();

    // Add agent response
    addChatMessage("agent", data.reply);
  } catch (error) {
    console.error("Chat error:", error);
    document.getElementById(typingId).remove();
    addChatMessage("agent", "Sorry, I encountered an error. Please try again.");
  }
}

function addChatMessage(sender, content) {
  const chatHistory = document.getElementById("chatHistory");
  const messageId = `msg-${Date.now()}`;

  const messageDiv = document.createElement("div");
  messageDiv.id = messageId;
  messageDiv.className = `chat-message ${sender}`;
  messageDiv.textContent = content;

  chatHistory.appendChild(messageDiv);
  chatHistory.scrollTop = chatHistory.scrollHeight;

  return messageId;
}

// Delete selected camera
async function deleteSelectedCamera() {
  if (!selectedCameraId) {
    alert("No camera selected");
    return;
  }

  const camera = cameras.find((c) => c.id === selectedCameraId);
  if (!camera) {
    alert("Camera not found");
    return;
  }

  // Confirm deletion
  const confirmed = confirm(
    `Are you sure you want to delete camera "${camera.name}"?`
  );
  if (!confirmed) return;

  try {
    const response = await fetch(`/camera/${selectedCameraId}`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    });

    const result = await response.json();

    if (response.ok && result.success) {
      alert(result.message || "Camera deleted successfully");

      // Clear video stream
      clearVideoStream();
      selectedCameraId = null;

      // Hide delete button
      document.getElementById("deleteCameraBtn").style.display = "none";
      document.getElementById("clearHistoryBtn").style.display = "none";

      // Reload camera list
      await loadCameras();
    } else {
      throw new Error(result.detail || "Failed to delete camera");
    }
  } catch (error) {
    console.error("Delete camera error:", error);
    alert("Failed to delete camera: " + error.message);
  }
}

// Clear camera history
async function clearCameraHistory() {
  if (!selectedCameraId) {
    alert("No camera selected");
    return;
  }

  const camera = cameras.find((c) => c.id === selectedCameraId);
  if (!camera) {
    alert("Camera not found");
    return;
  }

  // Confirm action
  const confirmed = confirm(
    `Are you sure you want to clear all history for camera "${camera.name}"?\n\nThis will permanently delete:\n- All recorded frames\n- Scene graph data\n- Event logs\n- Notifications\n\nThis action cannot be undone.`
  );
  if (!confirmed) return;

  try {
    const response = await fetch(`/camera/${selectedCameraId}/history`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    });

    const result = await response.json();

    if (response.ok && result.success) {
      const deleted = result.deleted;
      const message =
        `History cleared for camera "${camera.name}":\n` +
        `- ${deleted.media_files} media files\n` +
        `- ${deleted.scene_graphs} scene graphs\n` +
        `- ${deleted.event_logs} event logs\n` +
        `- ${deleted.notifications} notifications`;

      alert(message);

      // Refresh events and notifications
      await loadEvents();
      await loadNotifications();
    } else {
      throw new Error(result.detail || "Failed to clear camera history");
    }
  } catch (error) {
    console.error("Clear camera history error:", error);
    alert("Failed to clear camera history: " + error.message);
  }
}

// Utility functions
function formatDateTime(dateString) {
  const date = new Date(dateString);
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatEventName(name) {
  return name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

// Initialize dashboard
async function initDashboard() {
  const authenticated = await checkAuth();
  if (!authenticated) return;

  await loadCameras();
  await loadEvents();
  await loadNotifications();

  // Auto-refresh every 30 seconds
  setInterval(() => {
    loadEvents();
    loadNotifications();
  }, 30000);

  // Add modal click handlers
  setupModalHandlers();
}

// Setup modal click handlers
function setupModalHandlers() {
  // Close modals when clicking outside
  window.addEventListener("click", function (event) {
    const chatModal = document.getElementById("chatModal");
    const sceneGraphModal = document.getElementById("sceneGraphModal");
    const addCameraModal = document.getElementById("addCameraModal");
    const globalSettingsModal = document.getElementById("globalSettingsModal");
    const eventDetailsModal = document.getElementById("eventDetailsModal");

    if (event.target === chatModal) {
      closeChatModal();
    }
    if (event.target === sceneGraphModal) {
      closeSceneGraphModal();
    }
    if (event.target === eventDetailsModal) {
      closeEventDetailsModal();
    }
    if (event.target === addCameraModal) {
      closeAddCameraModal();
    }
    if (event.target === globalSettingsModal) {
      closeGlobalSettingsModal();
    }
  });
}

// ============================================
// CAMERA CONFIGURATION FUNCTIONS
// ============================================

// Load camera configuration
async function loadCameraConfig(cameraId) {
  if (!cameraId) return;

  try {
    const response = await fetch(`/camera/${cameraId}/config`, {
      headers: getAuthHeaders(),
    });

    if (response.ok) {
      const data = await response.json();
      const config = data.config;

      // Update UI
      const intervalInput = document.getElementById("captureInterval");
      if (intervalInput) {
        intervalInput.value = config.capture_interval || 2;
      }
    }
  } catch (error) {
    console.error("Failed to load camera config:", error);
  }
}

// Update capture rate for selected camera
async function updateCaptureRate() {
  if (!selectedCameraId) {
    alert("Please select a camera first");
    return;
  }

  const intervalInput = document.getElementById("captureInterval");
  const interval = parseFloat(intervalInput.value);

  if (interval < 0.5 || interval > 60) {
    alert("Capture interval must be between 0.5 and 60 seconds");
    return;
  }

  try {
    const response = await fetch(`/camera/${selectedCameraId}/config`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        capture_interval: interval,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      const restartMsg = data.restarted ? " (camera restarted)" : "";
      alert(`Capture rate updated to ${interval}s${restartMsg}`);
    } else {
      throw new Error(data.detail || "Failed to update capture rate");
    }
  } catch (error) {
    console.error("Update capture rate error:", error);
    alert("Failed to update capture rate: " + error.message);
  }
}

// Show global settings modal
function showGlobalSettings() {
  const modal = document.getElementById("globalSettingsModal");
  modal.style.display = "flex";

  // Load current global settings
  loadGlobalSettings();
}

// Close global settings modal
function closeGlobalSettingsModal() {
  document.getElementById("globalSettingsModal").style.display = "none";
}

// Load global settings
async function loadGlobalSettings() {
  try {
    const response = await fetch("/config/global", {
      headers: getAuthHeaders(),
    });

    if (response.ok) {
      const data = await response.json();
      const config = data.config;

      document.getElementById("defaultCaptureInterval").value =
        config.default_capture_interval || 2;
      document.getElementById("autoDetection").checked =
        config.auto_detection !== false;
      document.getElementById("saveFrames").checked =
        config.save_frames !== false;
    }
  } catch (error) {
    console.error("Failed to load global settings:", error);
  }
}

// Handle global settings form submission
document.addEventListener("DOMContentLoaded", function () {
  const globalSettingsForm = document.getElementById("globalSettingsForm");
  if (globalSettingsForm) {
    globalSettingsForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const defaultInterval = parseFloat(
        document.getElementById("defaultCaptureInterval").value
      );
      const autoDetection = document.getElementById("autoDetection").checked;
      const saveFrames = document.getElementById("saveFrames").checked;

      if (defaultInterval < 0.5 || defaultInterval > 60) {
        alert("Default capture interval must be between 0.5 and 60 seconds");
        return;
      }

      try {
        const response = await fetch("/config/global", {
          method: "POST",
          headers: getAuthHeaders(),
          body: JSON.stringify({
            default_capture_interval: defaultInterval,
            auto_detection: autoDetection,
            save_frames: saveFrames,
          }),
        });

        const data = await response.json();

        if (response.ok) {
          alert("Global settings saved successfully!");
          closeGlobalSettingsModal();
        } else {
          throw new Error(data.detail || "Failed to save settings");
        }
      } catch (error) {
        console.error("Save global settings error:", error);
        alert("Failed to save settings: " + error.message);
      }
    });
  }
});

// Start when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDashboard);
} else {
  initDashboard();
}
