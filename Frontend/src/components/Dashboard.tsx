import { useEffect, useState } from 'react';
import './Dashboard.css';

interface User {
  id: string;
  name: string;
  email: string;
  profession: string;
}

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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
        <button onClick={handleLogout} className="logout-btn">
          Logout
        </button>
      </nav>

      <main className="dashboard-main">
        <div className="welcome-section">
          <h1>Welcome, {user.name}</h1>
          <p>You are witnessing the growth as a {getProfessionLabel(user.profession)}</p>
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-card">
            <h3>Profile Information</h3>
            <div className="profile-info">
              <div className="info-item">
                <label>Name:</label>
                <span>{user.name}</span>
              </div>
              <div className="info-item">
                <label>Email:</label>
                <span>{user.email}</span>
              </div>
              <div className="info-item">
                <label>Profession:</label>
                <span>{getProfessionLabel(user.profession)}</span>
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
      </main>
    </div>
  );
}
