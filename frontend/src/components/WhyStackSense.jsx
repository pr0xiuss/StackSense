import React from 'react';

export default function WhyStackSense() {
  const benefits = [
    {
      title: 'Faster onboarding',
      desc: 'Understand unfamiliar codebases sooner.',
      colorClass: '',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      )
    },
    {
      title: 'Clearer architecture',
      desc: 'See how components and services connect.',
      colorClass: 'teal',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
          <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
        </svg>
      )
    },
    {
      title: 'Safer changes',
      desc: 'Understand dependencies before modifying code.',
      colorClass: 'purple',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 14 14" />
        </svg>
      )
    }
  ];

  return (
    <section className="why-section" id="why-stacksense" aria-labelledby="why-heading">
      <div className="container">
        <div className="section-header">
          <div className="section-label">Engineered for Clarity</div>
          <h2 className="section-title" id="why-heading">
            Understand systems without tracing everything manually.
          </h2>
          <p className="section-subtitle">
            Whether you&apos;re joining an unfamiliar project, reviewing an architecture,
            or maintaining a legacy system, StackSense helps you see how the pieces fit together.
          </p>
        </div>

        <div className="why-grid">
          {benefits.map((benefit, index) => (
            <div key={index} className="why-card">
              <div className={`why-icon-box ${benefit.colorClass}`}>
                {benefit.icon}
              </div>
              <h3 className="why-card-title">{benefit.title}</h3>
              <p className="why-card-desc">{benefit.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
