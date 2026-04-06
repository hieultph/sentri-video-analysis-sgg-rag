// Simple and reliable stream display functions

function updateVideoStream(camera) {
  const container = document.getElementById("videoContainer");
  const statusBadge = document.getElementById("videoStatus");

  // Clear container
  container.innerHTML = "";

  const streamUrl = camera.stream_url;
  console.log("Attempting to display stream:", streamUrl);

  // Create simple img element for stream
  const streamHTML = `
    <div style="width: 100%; position: relative;">
      <img 
        src="${streamUrl}" 
        style="width: 100%; height: auto; max-height: 500px; object-fit: contain; display: block;" 
        onload="this.parentNode.parentNode.querySelector('.stream-status').textContent = '✓ Connected: ${camera.name}'; this.parentNode.parentNode.querySelector('.stream-status').className = 'status-badge active';"
        onerror="this.parentNode.parentNode.querySelector('.stream-status').textContent = '✗ Failed to connect'; this.parentNode.parentNode.querySelector('.stream-status').className = 'status-badge error'; this.style.display = 'none'; this.parentNode.querySelector('.error-msg').style.display = 'block';"
        alt="Live Stream from ${camera.name}"
      />
      <div class="error-msg" style="display: none; text-align: center; padding: 40px; color: #999;">
        <p>❌ Could not load stream</p>
        <p style="font-size: 0.9em; margin: 10px 0;">URL: ${streamUrl}</p>
        <button onclick="location.reload()" style="padding: 8px 16px; margin-top: 10px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer;">
          🔄 Retry
        </button>
        <button onclick="window.open('${streamUrl}', '_blank')" style="padding: 8px 16px; margin: 5px; background: #64748b; color: white; border: none; border-radius: 4px; cursor: pointer;">
          🔗 Open Direct
        </button>
      </div>
    </div>
  `;

  container.innerHTML = streamHTML;
  statusBadge.textContent = `🔄 Loading ${camera.name}...`;
  statusBadge.className = "status-badge stream-status";
}

function clearVideoStream() {
  const container = document.getElementById("videoContainer");
  const statusBadge = document.getElementById("videoStatus");

  container.innerHTML =
    '<div class="video-placeholder"><p>Select a camera to view stream</p></div>';
  statusBadge.textContent = "No camera selected";
  statusBadge.className = "status-badge";
}
