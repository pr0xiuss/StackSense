/**
 * Sample TSX component for M3 IR normalization fixtures.
 */
import React from 'react';
import { Header } from './Header';
import { Footer } from './Footer';

interface DashboardProps {
  title: string;
}

export const Dashboard: React.FC<DashboardProps> = ({ title }) => {
  return (
    <div className="dashboard-container">
      <Header title={title} />
      <main>
        <h1>Welcome to {title}</h1>
      </main>
      <Footer />
    </div>
  );
};
