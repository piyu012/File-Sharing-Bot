from bot import Bot
from api 
import dns.resolver import setup_routes
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']

app = web.AppRunner(await web_server())
await app.setup()
site = web.TCPSite(app, "0.0.0.0", PORT)

Bot().run()
