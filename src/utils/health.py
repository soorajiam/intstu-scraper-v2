"""Health check endpoint for Docker."""

from aiohttp import web
import psutil

async def health_handler(request):
    """Handle health check requests."""
    try:
        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 95:  # Critical memory threshold
            return web.Response(status=503, text="Memory usage critical")
            
        return web.Response(status=200, text="OK")
    except Exception:
        return web.Response(status=500, text="Health check failed")

async def start_health_server():
    """Start the health check server."""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start() 