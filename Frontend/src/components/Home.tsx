import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Spline from '@splinetool/react-spline';
import '../App.css';

export default function Home() {
  const navigate = useNavigate();

  // Hide Spline logo functionality
  useEffect(() => {
    const hideSplineLogo = () => {
      const logoSelectors = [
        'div[style*="position: absolute"][style*="bottom"][style*="right"]',
        'div[style*="position: fixed"][style*="bottom"][style*="right"]',
        'a[href*="spline.design"]',
        '[class*="spline"][class*="logo"]',
        '[class*="watermark"]'
      ];
      
      logoSelectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(element => {
          const htmlElement = element as HTMLElement;
          if (htmlElement.innerText?.toLowerCase().includes('spline') || 
              htmlElement.innerHTML?.toLowerCase().includes('spline')) {
            htmlElement.style.display = 'none';
          }
        });
      });
    };

    hideSplineLogo();
    const interval = setInterval(hideSplineLogo, 1000);
    
    return () => clearInterval(interval);
  }, []);

  const handleWitnessGrowthClick = () => {
    navigate('/signup');
  };

  return (
    <main className="spline-container">
      <Spline
        scene="https://prod.spline.design/y9ImRL3BdgwTVVnZ/scene.splinecode" 
      />
      {/* Clickable overlay for WITNESS THE GROWTH button */}
      <div 
        className="witness-growth-overlay"
        onClick={handleWitnessGrowthClick}
        title="Click to witness the growth"
      />
    </main>
  );
}