import api from './client'


export const getAccount = async () =>
  (await api.get('/accounts/me')).data


export const getSimulationSettings = async () =>
  (await api.get('/simulation/settings')).data


export const setInitialAsset = async (initialAsset) =>
  (
    await api.post(
      '/simulation/initial-asset',
      {
        initial_asset: initialAsset,
      },
    )
  ).data


export const updateSimulationSettings = async (
  monthlyIncome,
  monthlyExpense,
) =>
  (
    await api.patch(
      '/simulation/settings',
      {
        monthly_income: monthlyIncome,
        monthly_expense: monthlyExpense,
      },
    )
  ).data


export const resetSimulation = async () =>
  (await api.delete('/simulation/reset')).data


export const payMonthlyIncome = async (yearMonth) =>
  (
    await api.post(
      '/monthly-income/pay',
      {
        year_month: yearMonth,
      },
    )
  ).data


export const getProducts = async (params = {}) =>
  (
    await api.get(
      '/products',
      {
        params,
      },
    )
  ).data


export const getProduct = async (productId) =>
  (
    await api.get(
      `/products/${productId}`,
    )
  ).data


export const simulateDeposit = async (payload) =>
  (
    await api.post(
      '/deposits/simulate',
      payload,
    )
  ).data


export const createDeposit = async (payload) =>
  (
    await api.post(
      '/deposits',
      payload,
    )
  ).data


export const getDeposits = async (params = {}) =>
  (
    await api.get(
      '/deposits',
      {
        params,
      },
    )
  ).data


export const getDeposit = async (depositId) =>
  (
    await api.get(
      `/deposits/${depositId}`,
    )
  ).data


export const terminateDeposit = async (depositId) =>
  (
    await api.post(
      `/deposits/${depositId}/terminate`,
    )
  ).data


export const simulateSaving = async (payload) =>
  (
    await api.post(
      '/savings/simulate',
      payload,
    )
  ).data


export const createSaving = async (payload) =>
  (
    await api.post(
      '/savings',
      payload,
    )
  ).data


export const getSavings = async (params = {}) =>
  (
    await api.get(
      '/savings',
      {
        params,
      },
    )
  ).data


export const getSaving = async (savingId) =>
  (
    await api.get(
      `/savings/${savingId}`,
    )
  ).data


export const getSavingPayments = async (
  savingId,
  params = {},
) =>
  (
    await api.get(
      `/savings/${savingId}/payments`,
      {
        params,
      },
    )
  ).data


export const terminateSaving = async (savingId) =>
  (
    await api.post(
      `/savings/${savingId}/terminate`,
    )
  ).data


// ----------------------------------------------------------------
// 투자


export const getInvestmentAssets = async (
  params = {},
) =>
  (
    await api.get(
      '/investments/assets',
      {
        params,
      },
    )
  ).data


export const getInvestmentPrice = async (
  symbol,
  market,
) =>
  (
    await api.get(
      '/investments/price',
      {
        params: {
          symbol,
          market,
        },
      },
    )
  ).data


export const createInvestmentOrder = async (
  payload,
) =>
  (
    await api.post(
      '/investments/orders',
      payload,
    )
  ).data


export function getApiError(
  error,
  fallback = '요청 처리 중 오류가 발생했습니다.',
) {
  return (
    error.response?.data?.error?.message
    || error.message
    || fallback
  )
}