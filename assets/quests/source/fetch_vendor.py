"""Vendor pinned Leaflet assets and required license notices."""
from pathlib import Path
import urllib.request

base=Path(__file__).resolve().parents[1]/'site/assets/quests'
files={
 'vendor/leaflet.js':'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
 'vendor/leaflet.css':'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
 'vendor/Leaflet-LICENSE.txt':'https://raw.githubusercontent.com/Leaflet/Leaflet/v1.9.4/LICENSE',
 'COPYING.txt':'https://www.gnu.org/licenses/gpl-3.0.txt',
}
for filename in ['layers.png','layers-2x.png','marker-icon.png','marker-icon-2x.png','marker-shadow.png']:
 files['vendor/images/'+filename]='https://unpkg.com/leaflet@1.9.4/dist/images/'+filename
for filename,url in files.items():
 target=base/filename;target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists():
  with urllib.request.urlopen(url,timeout=30) as response:target.write_bytes(response.read())
print('Vendored Leaflet 1.9.4, BSD license and GPLv3 notice.')
