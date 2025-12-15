import argparse
import asyncio
import json
import logging
import os
import ssl
import uuid
import socket

import cv2
from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame

# 1. VIDEO PROCESSING TRACK
class VideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """
    kind = "video"

    def __init__(self, track):
        super().__init__()  # don't forget this!
        self.track = track

    async def recv(self):
        # Get the frame from the incoming track (browser)
        frame = await self.track.recv()

        # Convert to numpy array (OpenCV format)
        img = frame.to_ndarray(format="bgr24")

        # --- PROCESS THE IMAGE HERE ---
        # Example: Canny Edge Detection
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.Canny(img, 100, 200)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        # ------------------------------

        # Rebuild a VideoFrame to send back to WebRTC
        new_frame = VideoFrame.from_ndarray(img, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        return new_frame

# Keep track of connections so we can close them (Management)
pcs = set()

# 2. SIGNALING HANDLERS
async def index(request):
    content = open(os.path.join(os.path.dirname(__file__), "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs.add(pc)

    # Management: Handle connection closing
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)

    # When the browser sends video, we grab it and attach our processor
    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            print("Video track received")
            # Create our transform track and add it to the response
            local_video = VideoTransformTrack(track)
            pc.addTrack(local_video)

    # Set the remote description (the browser's offer)
    await pc.setRemoteDescription(offer)

    # Create an answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    if os.environ.get("FORCE_LOCALHOST") == "true":
        print("DEBUG: Applying localhost patch for Mac/Docker")
        container_ip = socket.gethostbyname(socket.gethostname())
        sdp_patched = pc.localDescription.sdp.replace(container_ip, "127.0.0.1")
        
        return web.json_response({
            "sdp": sdp_patched,
            "type": pc.localDescription.type
        })
    
    # Standard behavior for Ubuntu (Production)
    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

# 3. CLEANUP
async def on_shutdown(app):
    # Close all open peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

# 4. MAIN ENTRY POINT
if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)
    app.on_shutdown.append(on_shutdown)
    
    print("Server running at http://localhost:8080")
    web.run_app(app, host="0.0.0.0", port=8080)