import React from 'react';

export default function HowItWorks() {
  const steps = [
    {
      num: '01',
      title: 'Connect',
      desc: 'Add a Git repository or upload a ZIP.'
    },
    {
      num: '02',
      title: 'Analyze',
      desc: 'Parse the code and identify structure and relationships.'
    },
    {
      num: '03',
      title: 'Build',
      desc: 'Create a structured architecture model.'
    },
    {
      num: '04',
      title: 'Explore',
      desc: 'Visualize, search, and understand the system.'
    }
  ];

  return (
    <section className="workflow-section" id="how-it-works" aria-labelledby="workflow-heading">
      <div className="container">
        <div className="section-header">
          <div className="section-label">Pipeline</div>
          <h2 className="section-title" id="workflow-heading">How StackSense Works</h2>
          <p className="section-subtitle">
            From source code to architectural understanding.
          </p>
        </div>

        <div className="workflow-steps-grid">
          {steps.map((step) => (
            <article key={step.num} className="workflow-card">
              <span className="workflow-step-num" aria-hidden="true">{step.num}</span>
              <h3 className="workflow-step-title">{step.title}</h3>
              <p className="workflow-step-desc">{step.desc}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
