import { Routes, Route } from 'react-router-dom'

import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import OAuthCallbackPage from './pages/OAuthCallbackPage'
import SocialSignupPage from './pages/SocialSignupPage'
import PasswordChangePage from './pages/PasswordChangePage'
import WithdrawPage from './pages/WithdrawPage'
import AccountPage from './pages/AccountPage'
import ProductsPage from './pages/ProductsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import MyProductsPage from './pages/MyProductsPage'
import InvestmentsPage from './pages/InvestmentsPage'
import DashboardPage from './pages/DashboardPage'
import GoalsPage from './pages/GoalsPage'
import TransactionsPage from './pages/TransactionsPage'
import CommunityPage from './pages/CommunityPage'
import ProfilePage from './pages/ProfilePage'
import SimulationPage from './pages/SimulationPage'
import BadgePage from './pages/BadgePage'
import SupportPage from './pages/SupportPage'
import AdminPage from './pages/AdminPage'
import ProtectedRoute from './components/ProtectedRoute'
import Toast from './components/Toast'


function App() {
  return (
    <>
    <Toast />
    <Routes>
      <Route
        path="/"
        element={<HomePage />}
      />

      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/signup"
        element={<SignupPage />}
      />

      <Route
        path="/oauth/google/callback"
        element={
          <OAuthCallbackPage provider="google" />
        }
      />

      <Route
        path="/oauth/kakao/callback"
        element={
          <OAuthCallbackPage provider="kakao" />
        }
      />

      <Route
        path="/social-signup"
        element={<SocialSignupPage />}
      />

      <Route
        path="/password"
        element={<PasswordChangePage />}
      />

      <Route
        path="/withdraw"
        element={<WithdrawPage />}
      />

      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/goals" element={<ProtectedRoute><GoalsPage /></ProtectedRoute>} />
      <Route path="/simulation" element={<ProtectedRoute><SimulationPage /></ProtectedRoute>} />
      <Route path="/badges" element={<ProtectedRoute><BadgePage /></ProtectedRoute>} />
      <Route path="/support" element={<ProtectedRoute><SupportPage /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
      <Route path="/transactions" element={<ProtectedRoute><TransactionsPage /></ProtectedRoute>} />
      <Route path="/community/posts/:postId" element={<ProtectedRoute><CommunityPage /></ProtectedRoute>} />
      <Route path="/community" element={<ProtectedRoute><CommunityPage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/profile/:userId" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/account" element={<ProtectedRoute><AccountPage /></ProtectedRoute>} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/products/:productId" element={<ProductDetailPage />} />
      <Route path="/my-products" element={<ProtectedRoute><MyProductsPage /></ProtectedRoute>} />
      <Route path="/investments" element={<ProtectedRoute><InvestmentsPage /></ProtectedRoute>} />
    </Routes>
    </>
  )
}


export default App
