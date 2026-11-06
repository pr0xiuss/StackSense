import React from "react";

export interface HeaderProps {
  title: string;
}

export const Header: React.FC<HeaderProps> = ({ title }) => {
  return <h1>{title}</h1>;
};

export const Dashboard: React.FC = () => {
  return (
    <div className="dashboard">
      <Header title="StackSense Overview" />
      <p>System status is nominal.</p>
    </div>
  );
};

