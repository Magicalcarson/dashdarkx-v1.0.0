/* eslint-disable react-refresh/only-export-components */
import { Suspense, lazy } from 'react';
import { Outlet, createBrowserRouter, Navigate } from 'react-router-dom';
import MainLayout from 'layouts/main-layout';
import AuthLayout from 'layouts/auth-layout';
import Splash from 'components/loading/Splash';
import PageLoader from 'components/loading/PageLoader';

const App = lazy(() => import('App'));
const Dashboard = lazy(() => import('pages/dashboard'));
const Login = lazy(() => import('pages/authentication/Login'));
const Signup = lazy(() => import('pages/authentication/Signup'));
const AdminPage = lazy(() => import('../pages/admin/AdminPanel'));
const CalibrationPage = lazy(() => import('../pages/calibration/CalibrationPage'));
const CalibrationPageCam2 = lazy(() => import('../pages/calibration/CalibrationPageCam2'));
const SmartControlPage = lazy(() => import('../pages/interactive/InteractivePage'));

// --- Route Guard ---
const RequireAuth = ({ children }: { children: JSX.Element }) => {
  const isAuth = localStorage.getItem('isAuthenticated') === 'true';
  if (!isAuth) {
    return <Navigate to="/authentication/login" replace />;
  }
  return children;
};

const router = createBrowserRouter(
  [
    {
      element: (
        <Suspense fallback={<Splash />}>
          <App />
        </Suspense>
      ),
      children: [
        {
          path: '/',
          element: (
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <Outlet />
              </Suspense>
            </MainLayout>
          ),
          children: [
            {
              index: true,
              element: <Dashboard />,
            },

            // ✅ Admin
            {
              path: 'admin',
              element: (
                <RequireAuth>
                  <AdminPage />
                </RequireAuth>
              ),
            },

            // ✅ Calibration Camera 1
            {
              path: 'calibration',
              element: (
                <RequireAuth>
                  <CalibrationPage />
                </RequireAuth>
              ),
            },

            // ✅ ✅ ✅ Calibration Camera 2 (FIXED PATH)
            {
              path: 'calibration-camera-2',
              element: (
                <RequireAuth>
                  <CalibrationPageCam2 />
                </RequireAuth>
              ),
            },

            // ✅ Smart Control
            {
              path: 'smart-control',
              element: (
                <RequireAuth>
                  <SmartControlPage />
                </RequireAuth>
              ),
            },
          ],
        },

        // ✅ Authentication
        {
          path: '/authentication',
          element: (
            <AuthLayout>
              <Outlet />
            </AuthLayout>
          ),
          children: [
            {
              path: 'login',
              element: <Login />,
            },
            {
              path: 'signup',
              element: <Signup />,
            },
          ],
        },
      ],
    },
  ],
  {
    basename: '/dashdarkX',
  },
);

export default router;
