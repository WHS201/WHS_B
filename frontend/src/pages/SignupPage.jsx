import {
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  Link,
  useNavigate,
} from 'react-router-dom'

import Header from '../components/Header'
import { showToast } from '../components/Toast'

import {
  signup,
} from '../api/auth'

import {
  isLoggedIn,
} from '../utils/token'


function SignupPage() {
  const navigate =
    useNavigate()

  const [
    username,
    setUsername,
  ] = useState('')

  const [
    nickname,
    setNickname,
  ] = useState('')

  const [
    password,
    setPassword,
  ] = useState('')

  const [
    passwordConfirm,
    setPasswordConfirm,
  ] = useState('')

  const [
    errorMessage,
    setErrorMessage,
  ] = useState('')

  const [
    loading,
    setLoading,
  ] = useState(false)

  const turnstileRef =
    useRef(null)

  const turnstileWidgetIdRef =
    useRef(null)

  const [
    turnstileToken,
    setTurnstileToken,
  ] = useState('')

  useEffect(() => {
    if (isLoggedIn()) {
      navigate(
        '/',
        {
          replace: true,
        },
      )
    }
  }, [navigate])

  useEffect(() => {
    const renderTurnstile = () => {
      if (
        !window.turnstile ||
        !turnstileRef.current ||
        turnstileWidgetIdRef.current !== null
      ) {
        return
      }

      turnstileWidgetIdRef.current =
        window.turnstile.render(
          turnstileRef.current,
          {
            sitekey:
              import.meta.env
                .VITE_TURNSTILE_SITE_KEY,

            action: 'signup',

            callback: (token) => {
              setTurnstileToken(token)
            },

            'expired-callback': () => {
              setTurnstileToken('')
            },

            'error-callback': () => {
              setTurnstileToken('')
            },
          },
        )
    }

    renderTurnstile()

    const intervalId =
      window.setInterval(() => {
        renderTurnstile()
      }, 100)

    return () => {
      window.clearInterval(intervalId)

      if (
        window.turnstile &&
        turnstileWidgetIdRef.current !== null
      ) {
        window.turnstile.remove(
          turnstileWidgetIdRef.current,
        )

        turnstileWidgetIdRef.current =
          null
      }
    }
  }, [])

  const handleSignup =
    async (event) => {
      event.preventDefault()

      if (
        !username.trim() ||
        !nickname.trim() ||
        !password ||
        !passwordConfirm
      ) {
        setErrorMessage(
          '모든 항목을 입력해주세요.',
        )

        return
      }


      if (
        password !==
        passwordConfirm
      ) {
        setErrorMessage(
          '비밀번호가 일치하지 않습니다.',
        )

        return
      }

      if (!turnstileToken) {
        setErrorMessage(
          'CAPTCHA 인증을 완료해주세요.',
        )

        return
      }

      try {
        setLoading(true)
        setErrorMessage('')

        await signup(
          username,
          password,
          nickname,
          turnstileToken,
        )

        showToast(
          '회원가입에 성공했습니다.',
        )

        navigate('/login')
      } catch (error) {
        const message =
          error.response
            ?.data
            ?.error
            ?.message ||
          '회원가입 중 오류가 발생했습니다.'

        setErrorMessage(
          message,
        )

        setTurnstileToken('')

        if (
          window.turnstile &&
          turnstileWidgetIdRef.current !== null
        ) {
          window.turnstile.reset(
            turnstileWidgetIdRef.current,
          )
        }
      } finally {

        setLoading(false)
      }
    }


  return (
    <div>
      <Header />

      <main className="auth-page">

        <section className="auth-card auth-card-wide">

          <div className="auth-card-header">

            <h1>
              회원가입
            </h1>

            <p>
              금융 시뮬레이션을 시작할
              계정을 만들어보세요.
            </p>

          </div>


          <form
            className="auth-form"
            onSubmit={handleSignup}
          >

            <div className="form-group">

              <label htmlFor="signup-username">
                아이디
              </label>

              <input
                id="signup-username"
                type="text"
                placeholder="사용할 아이디를 입력하세요"
                value={username}
                onChange={(event) =>
                  setUsername(
                    event.target.value,
                  )
                }
                autoComplete="username"
              />

              <p className="field-hint">
                4~20자로 입력해주세요.
              </p>

            </div>


            <div className="form-group">

              <label htmlFor="nickname">
                닉네임
              </label>

              <input
                id="nickname"
                type="text"
                placeholder="사용할 닉네임을 입력하세요"
                value={nickname}
                onChange={(event) =>
                  setNickname(
                    event.target.value,
                  )
                }
              />

              <p className="field-hint">
                2~20자로 입력해주세요.
              </p>

            </div>


            <div className="form-group">

              <label htmlFor="signup-password">
                비밀번호
              </label>

              <input
                id="signup-password"
                type="password"
                placeholder="비밀번호를 입력하세요"
                value={password}
                onChange={(event) =>
                  setPassword(
                    event.target.value,
                  )
                }
                autoComplete="new-password"
              />

              <p className="field-hint">
                영문, 숫자, 특수문자를 포함한
                8~20자로 입력해주세요.
              </p>

            </div>


            <div className="form-group">

              <label htmlFor="password-confirm">
                비밀번호 확인
              </label>

              <input
                id="password-confirm"
                type="password"
                placeholder="비밀번호를 다시 입력하세요"
                value={passwordConfirm}
                onChange={(event) =>
                  setPasswordConfirm(
                    event.target.value,
                  )
                }
                autoComplete="new-password"
              />

            </div>

            <div
              ref={turnstileRef}
            />

            {errorMessage && (
              <p className="error-message">
                {errorMessage}
              </p>
            )}


            <button
              type="submit"
              className="submit-button"
              disabled={loading}
            >
              {loading
                ? '가입 중...'
                : '회원가입'}
            </button>

          </form>


          <div className="auth-footer">

            <span>
              이미 계정이 있으신가요?
            </span>

            <Link to="/login">
              로그인
            </Link>

          </div>

        </section>

      </main>

    </div>
  )
}


export default SignupPage
