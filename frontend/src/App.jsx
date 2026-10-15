import React from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import Employees from "./pages/Employees.jsx";
import Attendance from "./pages/Attendance.jsx";
import PunchIn from "./pages/PunchIn.jsx";
import PunchOut from "./pages/PunchOut.jsx";
import Regularize from "./pages/Regularize.jsx";
import EmployeeMonthly from "./pages/EmployeeMonthly.jsx";
import DepartmentSummary from "./pages/DepartmentSummary.jsx";
import Leaderboard from "./pages/Leaderboard.jsx";
import DepartmentTrend from "./pages/DepartmentTrend.jsx";
import SystemHealth from "./pages/SystemHealth.jsx";

const NAV = [
  { group: "Overview", items: [["/", "Dashboard"]] },
  { group: "People", items: [["/employees", "Employees"]] },
  {
    group: "Attendance",
    items: [
      ["/attendance", "Records"],
      ["/punch-in", "Punch in"],
      ["/punch-out", "Punch out"],
      ["/regularize", "Regularization"],
    ],
  },
  {
    group: "Analytics",
    items: [
      ["/analytics/employee", "Employee monthly"],
      ["/analytics/departments", "Department summary"],
      ["/analytics/late", "Late-comers"],
      ["/analytics/trend", "Department trend"],
    ],
  },
];

export default function App() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Workforce360</div>
        <nav>
          {NAV.map((g) => (
            <div key={g.group} className="nav-group">
              <div className="nav-title">{g.group}</div>
              {g.items.map(([to, label]) => (
                <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/employees" element={<Employees />} />
          <Route path="/attendance" element={<Attendance />} />
          <Route path="/punch-in" element={<PunchIn />} />
          <Route path="/punch-out" element={<PunchOut />} />
          <Route path="/regularize" element={<Regularize />} />
          <Route path="/analytics/employee" element={<EmployeeMonthly />} />
          <Route path="/analytics/departments" element={<DepartmentSummary />} />
          <Route path="/analytics/late" element={<Leaderboard />} />
          <Route path="/analytics/trend" element={<DepartmentTrend />} />
         {/* <Route path="/system" element={<SystemHealth />} /> */}
         {/* <Route path="*" element={<Navigate to="/" replace />} /> */}
        </Routes>
      </main>
    </div>
  );
}
