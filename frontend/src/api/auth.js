import api from './client'


export async function signup(
  username,
  password,
  nickname,
  turnstileToken,
) {
  const response = await api.post(
    '/auth/signup',
    {
      username,
      password,
      nickname,
      turnstile_token: turnstileToken,
    },
  )

  return response.data
}


export async function login(
  username,
  password,
) {
  const response = await api.post(
    '/auth/login',
    {
      username,
      password,
    },
  )

  return response.data
}


export async function logout() {
  const response = await api.post(
    '/auth/logout',
    {},
  )

  return response.data
}


export async function socialLogin(
  provider,
  code,
) {
  const response = await api.post(
    `/auth/${provider}`,
    {
      code,
    },
  )

  return response.data
}


export async function socialSignup(
  socialSignupToken,
  username,
) {
  const response = await api.post(
    '/auth/social/signup',
    {
      social_signup_token:
        socialSignupToken,

      username,
    },
  )

  return response.data
}