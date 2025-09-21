import './App.css'
import Spline from '@splinetool/react-spline';
import { useEffect } from 'react';

export default function Home() {
  // Additional JavaScript method to hide Spline logo
  useEffect(() => {
    const hideSplineLogo = () => {
      // Target common Spline logo selectors
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

    // Run immediately and then periodically in case logo loads later
    hideSplineLogo();
    const interval = setInterval(hideSplineLogo, 1000);
    
    // Cleanup interval
    return () => clearInterval(interval);
  }, []);

  return (
    <main className="spline-container">
      <Spline
        scene="https://prod.spline.design/y9ImRL3BdgwTVVnZ/scene.splinecode" 
        />
      </main>
    );
  }
