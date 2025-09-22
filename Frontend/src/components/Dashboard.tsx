import { useEffect, useState } from 'react';
// @ts-ignore - google-map-react types may not be available
import GoogleMapReact from 'google-map-react';
import './Dashboard.css';

interface User {
  id: string;
  name: string;
  email: string;
  profession: string;
}

type TabType = 'dashboard' | 'maps' | 'settings';

interface MapMarkerProps {
  lat: number;
  lng: number;
  text: string;
}

const MapMarker = ({ text }: MapMarkerProps) => (
  <div className="map-marker">
    <div className="marker-pin"></div>
    <div className="marker-text">{text}</div>
  </div>
);

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  useEffect(() => {
    // Get user data from localStorage
    const userData = localStorage.getItem('user');
    const token = localStorage.getItem('token');

    if (!userData || !token) {
      window.location.href = '/login';
      return;
    }

    try {
      const parsedUser = JSON.parse(userData);
      setUser(parsedUser);
    } catch (error) {
      console.error('Error parsing user data:', error);
      window.location.href = '/login';
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
  };

  const getProfessionLabel = (profession: string) => {
    const labels: { [key: string]: string } = {
      'citizen': 'Citizen',
      'builder': 'Builder',
      'urban_contractor': 'Urban Contractor',
      'other': 'Other'
    };
    return labels[profession] || profession;
  };

  const renderDashboardContent = () => (
    <>
      <div className="welcome-section">
        <h1>Welcome, {user!.name}</h1>
        <p>You are witnessing the growth as a {getProfessionLabel(user!.profession)}</p>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Profile Information</h3>
          <div className="profile-info">
            <div className="info-item">
              <label>Name:</label>
              <span>{user!.name}</span>
            </div>
            <div className="info-item">
              <label>Email:</label>
              <span>{user!.email}</span>
            </div>
            <div className="info-item">
              <label>Profession:</label>
              <span>{getProfessionLabel(user!.profession)}</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Urban Growth Metrics</h3>
          <div className="metrics">
            <div className="metric-item">
              <span className="metric-value">127</span>
              <span className="metric-label">Projects Witnessed</span>
            </div>
            <div className="metric-item">
              <span className="metric-value">45</span>
              <span className="metric-label">Communities Impacted</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Recent Activity</h3>
          <div className="activity-list">
            <div className="activity-item">
              <span className="activity-time">Today</span>
              <span className="activity-desc">Joined the urban growth platform</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Actions</h3>
          <div className="action-buttons">
            <button className="action-btn primary">
              Explore Projects
            </button>
            <button className="action-btn secondary">
              View Analytics
            </button>
            <a href="/" className="action-btn tertiary">
              Back to 3D Scene
            </a>
          </div>
        </div>
      </div>
    </>
  );

  const renderMapsContent = () => {
    const defaultProps = {
      center: {
        lat: 10.99835602,
        lng: 77.01502627
      },
      zoom: 11
    };

    const handleApiLoaded = (map: unknown, maps: unknown) => {
      // use map and maps objects for advanced functionality
      console.log('Google Maps API loaded', { map, maps });
    };

    // Get the API key from environment variables (Vite)
    const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

    if (!googleMapsApiKey) {
      return (
        <>
          <div className="welcome-section">
            <h1>Urban Growth Maps</h1>
            <p>Google Maps API key is not configured</p>
          </div>
          <div className="dashboard-card">
            <h3>Configuration Required</h3>
            <p>Please add your Google Maps API key to the environment variables.</p>
            <p>Add <code>VITE_GOOGLE_MAPS_API_KEY=your_api_key_here</code> to your .env file</p>
          </div>
        </>
      );
    }

    return (
      <>
        <div className="welcome-section">
          <h1>Urban Growth Maps</h1>
          <p>Explore urban development and growth patterns in your area</p>
        </div>

        <div className="maps-container">
          <div className="map-controls">
            <div className="dashboard-card">
              <h3>Map Controls</h3>
              <div className="settings-section">
                <div className="setting-item">
                  <label>Map Type</label>
                  <select className="setting-select">
                    <option value="roadmap">Roadmap</option>
                    <option value="satellite">Satellite</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="terrain">Terrain</option>
                  </select>
                </div>
                <div className="setting-item">
                  <label>Show Growth Data</label>
                  <input type="checkbox" defaultChecked />
                </div>
                <div className="setting-item">
                  <label>Show Projects</label>
                  <input type="checkbox" defaultChecked />
                </div>
              </div>
            </div>
          </div>

          <div className="map-wrapper">
            <GoogleMapReact
              bootstrapURLKeys={{ key: googleMapsApiKey }}
              defaultCenter={defaultProps.center}
              defaultZoom={defaultProps.zoom}
              yesIWantToUseGoogleMapApiInternals
              onGoogleApiLoaded={({ map, maps }: { map: unknown; maps: unknown }) => handleApiLoaded(map, maps)}
              options={{
                styles: [
                  {
                    featureType: "all",
                    elementType: "geometry.fill",
                    stylers: [{ color: "#242f3e" }]
                  },
                  {
                    featureType: "all",
                    elementType: "labels.text.fill",
                    stylers: [{ color: "#746855" }]
                  },
                  {
                    featureType: "all",
                    elementType: "labels.text.stroke",
                    stylers: [{ color: "#242f3e" }]
                  },
                  {
                    featureType: "road",
                    elementType: "geometry",
                    stylers: [{ color: "#38414e" }]
                  },
                  {
                    featureType: "road.highway",
                    elementType: "geometry",
                    stylers: [{ color: "#746855" }]
                  },
                  {
                    featureType: "water",
                    elementType: "geometry",
                    stylers: [{ color: "#17263c" }]
                  }
                ]
              }}
            >
              <MapMarker
                lat={10.99835602}
                lng={77.01502627}
                text="Urban Growth Center"
              />
              <MapMarker
                lat={11.0168}
                lng={76.9558}
                text="Development Zone A"
              />
              <MapMarker
                lat={10.9845}
                lng={77.0856}
                text="Construction Site B"
              />
            </GoogleMapReact>
          </div>
        </div>

        <div className="dashboard-grid" style={{ marginTop: '2rem' }}>
          <div className="dashboard-card">
            <h3>Map Legend</h3>
            <div className="legend-items">
              <div className="legend-item">
                <span className="legend-color urban-center"></span>
                <span>Urban Growth Centers</span>
              </div>
              <div className="legend-item">
                <span className="legend-color development-zone"></span>
                <span>Development Zones</span>
              </div>
              <div className="legend-item">
                <span className="legend-color construction-site"></span>
                <span>Construction Sites</span>
              </div>
            </div>
          </div>

          <div className="dashboard-card">
            <h3>Quick Stats</h3>
            <div className="metrics">
              <div className="metric-item">
                <span className="metric-value">23</span>
                <span className="metric-label">Active Projects</span>
              </div>
              <div className="metric-item">
                <span className="metric-value">8</span>
                <span className="metric-label">Growth Zones</span>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  };

  const renderSettingsContent = () => (
    <>
      <div className="welcome-section">
        <h1>Settings</h1>
        <p>Manage your preferences and account settings</p>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Account Settings</h3>
          <div className="settings-section">
            <div className="setting-item">
              <label>Change Password</label>
              <button className="action-btn secondary">Update Password</button>
            </div>
            <div className="setting-item">
              <label>Email Notifications</label>
              <input type="checkbox" defaultChecked />
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Privacy Settings</h3>
          <div className="settings-section">
            <div className="setting-item">
              <label>Profile Visibility</label>
              <select className="setting-select">
                <option value="public">Public</option>
                <option value="private">Private</option>
              </select>
            </div>
            <div className="setting-item">
              <label>Data Sharing</label>
              <input type="checkbox" />
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Preferences</h3>
          <div className="settings-section">
            <div className="setting-item">
              <label>Theme</label>
              <select className="setting-select">
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="auto">Auto</option>
              </select>
            </div>
            <div className="setting-item">
              <label>Language</label>
              <select className="setting-select">
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
              </select>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Danger Zone</h3>
          <div className="settings-section">
            <div className="setting-item">
              <label>Delete Account</label>
              <button className="action-btn danger">Delete Account</button>
            </div>
          </div>
        </div>
      </div>
    </>
  );

  if (isLoading) {
    return (
      <div className="dashboard-container">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="dashboard-container">
      <nav className="dashboard-nav">
        <div className="nav-brand">
          <h2>THRESHOLD</h2>
        </div>
        
        <div className="nav-tabs">
          <button 
            className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={`tab-btn ${activeTab === 'maps' ? 'active' : ''}`}
            onClick={() => setActiveTab('maps')}
          >
            Maps
          </button>
          <button 
            className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            Settings
          </button>
        </div>

        <button onClick={handleLogout} className="logout-btn">
          Logout
        </button>
      </nav>

      <main className="dashboard-main">
        {activeTab === 'dashboard' && renderDashboardContent()}
        {activeTab === 'maps' && renderMapsContent()}
        {activeTab === 'settings' && renderSettingsContent()}
      </main>
    </div>
  );
}