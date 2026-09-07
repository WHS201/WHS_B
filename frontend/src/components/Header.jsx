import {
  Link,
  useNavigate,
} from 'react-router-dom'

import {
  logout,
} from '../api/auth'

import useAuth from '../hooks/useAuth'
import { showToast } from './Toast'

import {
  removeTokens,
} from '../utils/token'


function Header() {
  const navigate =
    useNavigate()

  const {
    loggedIn,
    provider,
  } = useAuth()


  const handleLogout =
    async () => {
      try {
        await logout()
      } catch {
        // 서버 로그아웃 요청이 실패하더라도
        // 브라우저에 저장된 로그인 정보는 제거한다.
      }

      removeTokens()

      showToast(
        '로그아웃되었습니다.',
      )

      navigate('/')
    }


  const isLocalAccount =
    provider === 'LOCAL'


  return (
    <header className="site-header">

      <div className="site-header-inner">

        <Link
          to="/"
          className="site-logo"
          aria-label="SeedTheMoa 홈"
        >
          Seed
          <span>TheMoa</span>
        </Link>


        <nav className="site-nav">

          <Link to="/">
            홈
          </Link>

          <Link to="/dashboard">
            대시보드
          </Link>

          <Link to="/goals">
            저축 목표
          </Link>

          <Link to="/simulation">
            시뮬레이션
          </Link>

          <Link to="/products">
            예·적금
          </Link>

          <Link to="/investments">
            투자
          </Link>

          <Link to="/transactions">
            거래 내역
          </Link>

          <Link to="/community">
            커뮤니티
          </Link>

        </nav>


        <div className="header-actions">

          {loggedIn ? (
            <>
              <Link
                to="/profile"
                className="header-text-link"
              >
                프로필
              </Link>

              <Link
                to="/support"
                className="header-text-link"
              >
                문의
              </Link>

              <Link
                to="/admin"
                className="header-text-link"
              >
                관리자
              </Link>

              {isLocalAccount && (
                <Link
                  to="/password"
                  className="header-text-link"
                >
                  비밀번호 변경
                </Link>
              )}

              <Link
                to="/withdraw"
                className="header-text-link"
              >
                회원탈퇴
              </Link>

              <button
                type="button"
                className="header-primary-button"
                onClick={handleLogout}
              >
                로그아웃
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="header-text-link"
              >
                로그인
              </Link>

              <Link
                to="/signup"
                className="header-primary-button"
              >
                회원가입
              </Link>
            </>
          )}

        </div>

      </div>

    </header>
  )
}


export default Header
