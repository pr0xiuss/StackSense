import React from 'react';
import Navbar from '../components/Navbar.jsx';
import Hero from '../components/Hero.jsx';
import ValueStrip from '../components/ValueStrip.jsx';
import HowItWorks from '../components/HowItWorks.jsx';
import WhyStackSense from '../components/WhyStackSense.jsx';
import ArchitectureSection from '../components/ArchitectureSection.jsx';
import CtaBanner from '../components/CtaBanner.jsx';
import Footer from '../components/Footer.jsx';

export default function LandingPage() {
  return (
    <div className="landing-page">
      <Navbar />
      <main id="main-content">
        <Hero />
        <ValueStrip />
        <HowItWorks />
        <WhyStackSense />
        <ArchitectureSection />
        <CtaBanner />
      </main>
      <Footer />
    </div>
  );
}
