import {
  useEffect,
  useState,
} from 'react'

import {
  Link,
  useNavigate,
} from 'react-router-dom'

import {
  logout,
} from '../api/auth'

import {
  getMyProfile,
} from '../api/features'

import useAuth from '../hooks/useAuth'
import { showToast } from './Toast'

import {
  removeTokens,
} from '../utils/token'


function Header() {
  const navigate = useNavigate()

  const {
    loggedIn,
    provider,
  } = useAuth()

  const [
    role,
    setRole,
  ] = useState(null)


  // 로그인한 사용자의 권한 조회
  useEffect(() => {
    if (!loggedIn) {
      setRole(null)
      return
    }

    getMyProfile()
      .then((response) => {
        setRole(
          response?.data?.role ?? null,
        )
      })
      .catch(() => {
        setRole(null)
      })
  }, [loggedIn])


  const handleLogout = async () => {
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

  const isAdmin =
    role === 'ADMIN'


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


          {loggedIn && (
            <details className="header-more-menu">

              <summary>
                더보기
              </summary>

              <div className="header-more-dropdown">

                <Link to="/simulation">
                  시뮬레이션
                </Link>

                <Link to="/profile">
                  프로필
                </Link>

                <Link to="/support">
                  문의
                </Link>

                {isAdmin && (
                  <Link to="/admin">
                    관리자
                  </Link>
                )}

                {isLocalAccount && (
                  <Link to="/password">
                    비밀번호 변경
                  </Link>
                )}

                <Link to="/withdraw">
                  회원탈퇴
                </Link>

              </div>

            </details>
          )}

        </nav>


        <div className="header-actions">

          {loggedIn ? (
            <button
              type="button"
              className="header-primary-button"
              onClick={handleLogout}
            >
              로그아웃
            </button>
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