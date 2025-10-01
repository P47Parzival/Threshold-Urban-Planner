import { useEffect, useState } from 'react';
import Maps from './Maps';
import Hotspots from './Hotspots';
import './Dashboard.css';

interface User {
  id: string;
  name: string;
  email: string;
  profession: string;
}

type TabType = 'dashboard' | 'maps' | 'hotspots' | 'settings';

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [showFloatingNav, setShowFloatingNav] = useState(false);

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
      {/* Regular navbar - hidden when on maps tab */}
      {activeTab !== 'maps' && activeTab !== 'hotspots' && (
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
              className="tab-btn"
              onClick={() => setActiveTab('maps')}
            >
              Maps
            </button>
            <button
              className="tab-btn"
              onClick={() => setActiveTab('hotspots')}
            >
              Hotspots
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
      )}

      {/* Floating navigation for maps tab */}
      {(activeTab === 'maps' || activeTab === 'hotspots') && (
        <>
          <button 
            className="floating-nav-toggle"
            onClick={() => setShowFloatingNav(!showFloatingNav)}
          >
            ☰
          </button>
          
          {showFloatingNav && (
            <div className="floating-nav-overlay">
              <div className="floating-nav-content">
                <div className="floating-nav-header">
                  <h3>THRESHOLD</h3>
                  <button 
                    className="floating-nav-close"
                    onClick={() => setShowFloatingNav(false)}
                  >
                    ✕
                  </button>
                </div>
                
                <div className="floating-nav-tabs">
                  <button 
                    className="floating-tab-btn"
                    onClick={() => {
                      setActiveTab('dashboard');
                      setShowFloatingNav(false);
                    }}
                  >
                    Dashboard
                  </button>
                  <button 
                    className={`floating-tab-btn ${activeTab === 'maps' ? 'active' : ''}`}
                    onClick={() => {
                      setActiveTab('maps');
                      setShowFloatingNav(false);
                    }}
                  >
                    Maps
                  </button>
                  <button 
                    className={`floating-tab-btn ${activeTab === 'hotspots' ? 'active' : ''}`}
                    onClick={() => {
                      setActiveTab('hotspots');
                      setShowFloatingNav(false);
                    }}
                  >
                    Hotspots
                  </button>
                  <button 
                    className="floating-tab-btn"
                    onClick={() => {
                      setActiveTab('settings');
                      setShowFloatingNav(false);
                    }}
                  >
                    Settings
                  </button>
                </div>
                
                <button 
                  onClick={handleLogout} 
                  className="floating-logout-btn"
                >
                  Logout
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <main className={`dashboard-main ${activeTab === 'maps' || activeTab === 'hotspots' ? 'dashboard-main-fullscreen' : ''}`}>
        {activeTab === 'dashboard' && renderDashboardContent()}
        {activeTab === 'maps' && <Maps />}
        {activeTab === 'hotspots' && <Hotspots />}
        {activeTab === 'settings' && renderSettingsContent()}
      </main>
    </div>
  );
}