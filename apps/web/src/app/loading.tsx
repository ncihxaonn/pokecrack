import React from "react";

export default function Loading() {
  return (
    <div className="page-shell" aria-live="polite" aria-busy="true">
      <p className="loading-label" role="status">Loading dashboard data</p>
      <div aria-hidden="true">
        <div className="loading-placeholder loading-title" />
        <div className="loading-placeholder loading-subtitle" />
        <div className="loading-workspace">
          <div className="loading-main">
            <div className="loading-placeholder loading-toolbar" />
            <div className="loading-placeholder loading-visual" />
          </div>
          <div className="loading-aside">
            {Array.from({ length: 3 }, (_, index) => <div className="loading-placeholder" key={index} />)}
          </div>
        </div>
      </div>
    </div>
  );
}
