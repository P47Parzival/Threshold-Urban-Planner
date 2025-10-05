// Dynamically load the Maps JavaScript API (alpha channel for 3D)
async function initMap() {
    const {Map} = await google.maps.importLibrary('maps');
    const {AdvancedMarkerElement} = await google.maps.importLibrary('marker');

    // Create the 3D map
    const map = new Map(document.getElementById('map'), {
        center: { lat: 37.7749, lng: -122.4194 }, // Example: San Francisco
        zoom: 15,
        mapId: 'your-map-id', // Optional: Create a styled map ID in Google Cloud for custom looks
        tilt: 88, // Reduced tilt for better performance (sweet spot for 3D effect without heavy load)
        heading: 0, // Rotation (0-360 degrees)
        mapTypeId: 'hybrid' // 'roadmap', 'satellite', or 'hybrid' for 3D buildings/terrain
    });

    // Optional: Add a 3D marker
    const marker = new AdvancedMarkerElement({
        map: map,
        position: { lat: 37.7749, lng: -122.4194 },
        title: 'Hello 3D World!'
    });
}

// Load the API script (async for better performance)
const script = document.createElement('script');
script.src = `https://maps.googleapis.com/maps/api/js?key=AIzaSyDcmtmHLCqgSiB3IwhVNw8_aV639cFgdDE&libraries=marker&loading=async&callback=initMap&v=alpha`;
document.head.appendChild(script);



