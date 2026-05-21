// Mapbox timeline loader
// Usage:
// 1. Ensure a MAPBOX_TOKEN global is available (see project token.env instructions).
// 2. Include Mapbox GL JS and CSS in your page.
// 3. Call initTimelineMap('mapContainerId', '/path/to/assets/map/<handle>.json')

async function initTimelineMap(containerId, dataUrl, options = {}) {
  if (typeof window === 'undefined') return null;
  if (!window.MAPBOX_TOKEN) {
    console.warn('MAPBOX_TOKEN not set on window. Set it from your token.env at build time.');
    return null;
  }

  mapboxgl.accessToken = window.MAPBOX_TOKEN;

  const resp = await fetch(dataUrl);
  if (!resp.ok) {
    console.error('Failed to load timeline map data:', resp.statusText);
    return null;
  }
  const data = await resp.json();

  const container = document.getElementById(containerId);
  if (!container) {
    console.error('Map container not found:', containerId);
    return null;
  }

  const map = new mapboxgl.Map({
    container: containerId,
    style: options.style || 'mapbox://styles/mapbox/streets-v11',
    center: options.center || [0, 0],
    zoom: options.zoom || 2,
  });

  map.on('load', () => {
    // Add markers
    const features = (data && data.features) || [];
    for (const feat of features) {
      const coords = feat.geometry && feat.geometry.coordinates;
      if (!coords || coords.length < 2) continue;
      const el = document.createElement('div');
      el.className = options.markerClass || 'timeline-marker';
      el.style.width = options.markerSize || '18px';
      el.style.height = options.markerSize || '18px';
      el.style.background = options.markerColor || '#d00';
      el.style.borderRadius = '50%';
      el.style.boxShadow = '0 0 2px rgba(0,0,0,0.5)';

      const popup = new mapboxgl.Popup({ offset: 10 }).setHTML(
        `<strong>${feat.properties && feat.properties.label ? feat.properties.label : ''}</strong><br/>${feat.properties && feat.properties.date ? feat.properties.date : ''}`
      );

      new mapboxgl.Marker(el).setLngLat(coords).setPopup(popup).addTo(map);
    }

    // Fit to bbox if provided
    if (data && data.bbox && data.bbox.length === 4) {
      const [minLon, minLat, maxLon, maxLat] = data.bbox;
      map.fitBounds([[minLon, minLat], [maxLon, maxLat]], { padding: options.padding || 40 });
    } else if (features.length) {
      // compute bounds
      let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
      for (const feat of features) {
        const [lon, lat] = feat.geometry.coordinates;
        if (lon < minLon) minLon = lon;
        if (lat < minLat) minLat = lat;
        if (lon > maxLon) maxLon = lon;
        if (lat > maxLat) maxLat = lat;
      }
      map.fitBounds([[minLon, minLat], [maxLon, maxLat]], { padding: options.padding || 40 });
    }
  });

  return map;
}

// export for module users
if (typeof module !== 'undefined') module.exports = { initTimelineMap };
