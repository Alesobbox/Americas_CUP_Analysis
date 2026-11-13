import { describe, expect, it, vi, afterEach } from 'vitest'
import http from 'node:http'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import {
  loadKinematicCatalog,
  requestKinematicSimulation,
  reverseKinematicScenario,
} from '../../engine/kinematicCatalog'
import {
  createKinematicMiddleware,
  reverseCatalogScenario,
} from '../../../scripts/kinematicScenarioMiddleware'
import type { KinematicScenario, KinematicScenarioV2, KinematicCatalog } from '../../types/kinematic'

describe('Kinematic Simulator Engine & Catalog Reversal Integrity', () => {
  const sampleScenario: KinematicScenario = {
    schema_version: 'kinematic-race-sim-1',
    team_a: 'ETNZ',
    team_b: 'GB1',
    tws_kt: 11.5,
    course_length_m: 2590,
    n_sims: 1000,
    mode: 'barcelona_2024_empirical',
    win_probability_a: 0.62,
    win_probability_b: 0.36,
    no_winner_probability: 0.02,
    joint_finisher_conditioning: {
      both_finished_count: 940,
      both_finished_fraction: 0.94,
      mean_delta_t_s: 4.5,
      p10_delta_t_s: -8.2,
      p50_delta_t_s: 4.1,
      p90_delta_t_s: 18.3,
      scope: 'Joint finisher only',
    },
    status_breakdown: {
      ETNZ: { finished_rate: 0.98, dns_rate: 0.01, dnf_exogenous_rate: 0.008, ocs_dsq_rate: 0.002 },
      GB1: { finished_rate: 0.96, dns_rate: 0.02, dnf_exogenous_rate: 0.015, ocs_dsq_rate: 0.005 },
    },
    attribution_7_component: {
      pre_start_positioning_s: 1.2,
      upwind_vmg_s: 2.1,
      downwind_vmg_s: 0.8,
      tack_execution_s: 0.3,
      gybe_execution_s: 0.1,
      boundary_avoidance_s: 0.0,
      technical_reliability_advantage: 0.02,
    },
  }

  const sampleV2Scenario: KinematicScenarioV2 = {
    schema_version: 'kinematic-race-sim-2',
    scenario_id: 'scen_18090e1adf90',
    model_id: 'ac75_0a7b20091ee7',
    status: 'available',
    probability_scope: 'completion_assumed_on_water',
    applied_inputs: {
      team_a: 'ac37:ETNZ',
      team_b: 'ac37:INEOS',
      course_id: 'barcelona_lvc_4leg',
      environment: { tws_mps: 6.0, twd_deg: 180.0 },
      purpose: 'preview',
      trial_count: 2000,
      seed: 2027,
      seconds_accounting: {
        straight_delta_s: 5.5,
        maneuver_delta_s: 2.0,
        start_delta_s: 1.0,
        total_mean_delta_s: 8.5,
      },
      variance_attribution: {
        empirical_paired_block_count: 624,
        empirical_cross_boat_correlation: 0.5873,
      },
    },
    probabilities: {
      win_a: 0.64,
      win_b: 0.36,
      no_winner: null,
      mc_error: 0.0107,
    },
    timing: {
      mean_time_a_s: 1320.0,
      mean_time_b_s: 1328.5,
      mean_delta_t_s: 8.5,
      central_80_margin_interval_s: [-12.4, 29.8],
    },
    time_accounting: {
      straight_delta_s: 5.5,
      maneuver_delta_s: 2.0,
      start_delta_s: 1.0,
      total_mean_delta_s: 8.5,
    },
    reason_codes: [],
  }

  describe('reversal symmetry (v1 and v2)', () => {
    it('swaps teams, win probabilities, and negates mean delta and attribution for v1', () => {
      const reversed = reverseKinematicScenario(sampleScenario)

      expect(reversed.team_a).toBe('GB1')
      expect(reversed.team_b).toBe('ETNZ')
      expect(reversed.win_probability_a).toBe(0.36)
      expect(reversed.win_probability_b).toBe(0.62)

      // Time delta reversal
      expect(reversed.joint_finisher_conditioning.mean_delta_t_s).toBe(-4.5)
      // Quantile reversal: [p10, p50, p90] -> [-p90, -p50, -p10]
      expect(reversed.joint_finisher_conditioning.p10_delta_t_s).toBe(-18.3)
      expect(reversed.joint_finisher_conditioning.p50_delta_t_s).toBe(-4.1)
      expect(reversed.joint_finisher_conditioning.p90_delta_t_s).toBe(8.2)

      // Attribution components negated
      expect(reversed.attribution_7_component.pre_start_positioning_s).toBe(-1.2)
      expect(reversed.attribution_7_component.upwind_vmg_s).toBe(-2.1)
      expect(reversed.attribution_7_component.downwind_vmg_s).toBe(-0.8)
      expect(reversed.attribution_7_component.tack_execution_s).toBe(-0.3)
      expect(reversed.attribution_7_component.gybe_execution_s).toBe(-0.1)
      expect(reversed.attribution_7_component.technical_reliability_advantage).toBe(-0.02)
    })

    it('swaps teams, win probabilities, central_80_margin_interval_s, and disjoint seconds accounting for v2', () => {
      const reversed = reverseKinematicScenario(sampleV2Scenario)

      expect(reversed.applied_inputs.team_a).toBe('ac37:INEOS')
      expect(reversed.applied_inputs.team_b).toBe('ac37:ETNZ')
      expect(reversed.probabilities?.win_a).toBe(0.36)
      expect(reversed.probabilities?.win_b).toBe(0.64)
      expect(reversed.probabilities?.no_winner).toBeNull()
      expect(reversed.probability_scope).toBe('completion_assumed_on_water')

      expect(reversed.timing?.mean_time_a_s).toBe(1328.5)
      expect(reversed.timing?.mean_time_b_s).toBe(1320.0)
      expect(reversed.timing?.mean_delta_t_s).toBe(-8.5)
      expect(reversed.timing?.central_80_margin_interval_s).toEqual([-29.8, 12.4])

      expect(reversed.applied_inputs.seconds_accounting?.straight_delta_s).toBe(-5.5)
      expect(reversed.applied_inputs.seconds_accounting?.maneuver_delta_s).toBe(-2.0)
      expect(reversed.applied_inputs.seconds_accounting?.start_delta_s).toBe(-1.0)
      expect(reversed.applied_inputs.seconds_accounting?.total_mean_delta_s).toBe(-8.5)
      expect(reversed.time_accounting?.total_mean_delta_s).toBe(-8.5)
    })

    it('satisfies involution (double-reversal equals original for both v1 and v2)', () => {
      const doubleReversed = reverseKinematicScenario(reverseKinematicScenario(sampleScenario))
      expect(doubleReversed.team_a).toBe(sampleScenario.team_a)
      expect(doubleReversed.team_b).toBe(sampleScenario.team_b)
      expect(doubleReversed.win_probability_a).toBe(sampleScenario.win_probability_a)
      expect(doubleReversed.win_probability_b).toBe(sampleScenario.win_probability_b)
      expect(doubleReversed.joint_finisher_conditioning.mean_delta_t_s).toBe(
        sampleScenario.joint_finisher_conditioning.mean_delta_t_s
      )
      expect(doubleReversed.joint_finisher_conditioning.p10_delta_t_s).toBe(
        sampleScenario.joint_finisher_conditioning.p10_delta_t_s
      )
      expect(doubleReversed.joint_finisher_conditioning.p90_delta_t_s).toBe(
        sampleScenario.joint_finisher_conditioning.p90_delta_t_s
      )

      const doubleV2 = reverseKinematicScenario(reverseKinematicScenario(sampleV2Scenario))
      expect(doubleV2.applied_inputs.team_a).toBe(sampleV2Scenario.applied_inputs.team_a)
      expect(doubleV2.applied_inputs.team_b).toBe(sampleV2Scenario.applied_inputs.team_b)
      expect(doubleV2.probabilities?.win_a).toBe(sampleV2Scenario.probabilities?.win_a)
      expect(doubleV2.timing?.mean_delta_t_s).toBe(sampleV2Scenario.timing?.mean_delta_t_s)
      expect(doubleV2.timing?.central_80_margin_interval_s).toEqual(
        sampleV2Scenario.timing?.central_80_margin_interval_s
      )
      expect(doubleV2.applied_inputs.seconds_accounting?.total_mean_delta_s).toBe(
        sampleV2Scenario.applied_inputs.seconds_accounting?.total_mean_delta_s
      )
    })

    it('middleware reverseCatalogScenario behaves identically to engine reversal for v1 and v2', () => {
      const midReversed = reverseCatalogScenario(sampleScenario)
      const engReversed = reverseKinematicScenario(sampleScenario)

      expect(midReversed.team_a).toBe(engReversed.team_a)
      expect(midReversed.team_b).toBe(engReversed.team_b)
      expect(midReversed.win_probability_a).toBe(engReversed.win_probability_a)
      expect(midReversed.win_probability_b).toBe(engReversed.win_probability_b)
      expect(midReversed.joint_finisher_conditioning.mean_delta_t_s).toBe(
        engReversed.joint_finisher_conditioning.mean_delta_t_s
      )
      expect(midReversed.joint_finisher_conditioning.p10_delta_t_s).toBe(
        engReversed.joint_finisher_conditioning.p10_delta_t_s
      )

      const midV2 = reverseCatalogScenario(sampleV2Scenario)
      const engV2 = reverseKinematicScenario(sampleV2Scenario)
      expect(midV2.applied_inputs.team_a).toBe(engV2.applied_inputs.team_a)
      expect(midV2.applied_inputs.team_b).toBe(engV2.applied_inputs.team_b)
      expect(midV2.probabilities.win_a).toBe(engV2.probabilities?.win_a)
      expect(midV2.timing.central_80_margin_interval_s).toEqual(
        engV2.timing?.central_80_margin_interval_s
      )
      expect(midV2.applied_inputs.seconds_accounting.total_mean_delta_s).toBe(
        engV2.applied_inputs.seconds_accounting?.total_mean_delta_s
      )
    })
  })

  describe('catalog fallback and error handling', () => {
    const originalFetch = globalThis.fetch

    afterEach(() => {
      globalThis.fetch = originalFetch
    })

    it('falls back to static /data/kinematic/catalog.json when /api/kinematic/catalog fails', async () => {
      const mockCatalog: KinematicCatalog = {
        schema_version: 'ac75-catalog-2',
        created_at: new Date().toISOString(),
        model_status: 'experimental',
        status_notice: 'Experimental testing catalog',
        total_scenarios: 2,
        available_teams: ['ac37:ETNZ', 'ac37:INEOS', 'ETNZ', 'GB1'],
        available_modes: [{ id: 'ac75_learned_v2', label: 'Learned v2', description: '' }],
        default_sliders: {},
        courses: [],
        scenarios: [sampleV2Scenario, sampleScenario],
      }

      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/kinematic/catalog') {
          return Promise.resolve({ ok: false, status: 404 } as Response)
        }
        if (url === '/data/kinematic/catalog.json') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => mockCatalog,
          } as Response)
        }
        return Promise.reject(new Error(`Unexpected fetch to ${url}`))
      })

      const catalog = await loadKinematicCatalog()
      expect(catalog.total_scenarios).toBe(2)
      expect((catalog.scenarios[0] as KinematicScenarioV2).applied_inputs.team_a).toBe('ac37:ETNZ')
    })

    it('rejects unsupported requests (HTTP 422) with an explicit error instead of returning invented numbers', async () => {
      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/kinematic/simulate') {
          return Promise.resolve({
            ok: false,
            status: 422,
            json: async () => ({
              status: 'unsupported_request',
              error: 'Wind speed out of supported range [6, 24] kt',
            }),
          } as Response)
        }
        return Promise.reject(new Error(`Unexpected fetch to ${url}`))
      })

      await expect(
        requestKinematicSimulation('ETNZ', 'GB1', 35.0, 'barcelona_2024_empirical')
      ).rejects.toThrow('Wind speed out of supported range [6, 24] kt')
    })

    it('verifies probabilities sum to 1.0 including no_winner_probability', () => {
      const total =
        sampleScenario.win_probability_a +
        sampleScenario.win_probability_b +
        (sampleScenario.no_winner_probability ?? 0)
      expect(total).toBeCloseTo(1.0, 5)

      const totalV2 =
        (sampleV2Scenario.probabilities?.win_a ?? 0) +
        (sampleV2Scenario.probabilities?.win_b ?? 0) +
        (sampleV2Scenario.probabilities?.no_winner ?? 0)
      expect(totalV2).toBeCloseTo(1.0, 5)
    })

    it('handles reversal of unavailable scenario cleanly', () => {
      const unavailScenario: KinematicScenarioV2 = {
        ...sampleV2Scenario,
        status: 'unavailable',
        probabilities: undefined,
        timing: undefined,
        reason_codes: ['insufficient_telemetry_support'],
      }
      const rev = reverseKinematicScenario(unavailScenario)
      expect(rev.status).toBe('unavailable')
      expect(rev.applied_inputs.team_a).toBe('ac37:INEOS')
      expect(rev.applied_inputs.team_b).toBe('ac37:ETNZ')
      expect(rev.reason_codes).toEqual(['insufficient_telemetry_support'])
      expect(rev.probabilities).toBeUndefined()
      expect(rev.timing).toBeUndefined()
    })

    it('rejects oversized payload (> 2 KiB) with 413 error', async () => {
      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/kinematic/simulate') {
          return Promise.resolve({
            ok: false,
            status: 413,
            json: async () => ({
              status: 'unsupported_request',
              error: 'Scenario request exceeds 2 KiB maximum payload limit.',
            }),
          } as Response)
        }
        return Promise.reject(new Error(`Unexpected fetch to ${url}`))
      })

      await expect(
        requestKinematicSimulation('ac37:ETNZ', 'ac37:INEOS', 12.0, 'ac75_learned_v2')
      ).rejects.toThrow('Scenario request exceeds 2 KiB maximum payload limit.')
    })

    it('isolates late response when newer request supersedes it via AbortSignal', async () => {
      const controller1 = new AbortController()
      controller1.abort()

      globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        if (init?.signal?.aborted) {
          const abortError = new Error('The user aborted a request.')
          abortError.name = 'AbortError'
          return Promise.reject(abortError)
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => sampleV2Scenario,
        } as Response)
      })

      await expect(
        requestKinematicSimulation('ac37:ETNZ', 'ac37:INEOS', 12.0, 'ac75_learned_v2', undefined, controller1.signal)
      ).rejects.toThrow(/aborted/)
    })
  })

  describe('kinematicScenarioMiddleware live HTTP integrity & exact cache', () => {
    async function startMiddlewareServer(workspaceRoot: string): Promise<{ baseUrl: string; close: () => Promise<void> }> {
      const middleware = createKinematicMiddleware(workspaceRoot)
      const server = http.createServer((req, res) => {
        middleware(req, res, () => {
          res.statusCode = 404
          res.end('Not found')
        })
      })
      await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', () => resolve()))
      const addr = server.address() as { port: number }
      return {
        baseUrl: `http://127.0.0.1:${addr.port}`,
        close: () => new Promise<void>((resolve, reject) => server.close((err) => (err ? reject(err) : resolve()))),
      }
    }

    it('misses cache on unrounded tws_mps (6.0004 vs 6.0) and standard/10000 trial counts, and rejects bad requests with 422', async () => {
      const srv = await startMiddlewareServer(process.cwd())
      try {
        const catRes = await fetch(`${srv.baseUrl}/api/kinematic/catalog`)
        expect(catRes.status).toBe(200)
        const catalog = (await catRes.json()) as KinematicCatalog
        const v2Scenarios = catalog.scenarios.filter(
          (s): s is KinematicScenarioV2 => (s as KinematicScenarioV2).schema_version === 'kinematic-race-sim-2'
        )
        expect(v2Scenarios.length).toBeGreaterThan(0)
        const baseScenario =
          v2Scenarios.find(
            (s) =>
              s.applied_inputs.team_a === 'ac37:ETNZ' &&
              s.applied_inputs.team_b === 'ac37:INEOS' &&
              s.applied_inputs.course_id === 'barcelona_lvc_4leg' &&
              s.applied_inputs.environment.tws_mps === 6.0 &&
              s.applied_inputs.purpose === 'preview'
          ) ?? v2Scenarios[0]
        const modelId = baseScenario.model_id

        // 1. Subtle tws_mps difference (6.0004 vs cached 6.0) must bypass cache and preserve exact input
        const res60004 = await fetch(`${srv.baseUrl}/api/kinematic/simulate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 6.0004, twd_deg: 180.0 },
            purpose: 'preview',
          }),
        })
        expect(res60004.status).toBe(200)
        const body60004 = (await res60004.json()) as KinematicScenarioV2
        expect(body60004.applied_inputs.environment.tws_mps).toBe(6.0004)
        expect(body60004.applied_inputs.purpose).toBe('preview')
        expect(body60004.applied_inputs.trial_count).toBe(2000)
        expect(body60004.scenario_id).not.toBe(baseScenario.scenario_id)

        // 2. standard purpose + 10000 trials must bypass cached preview (2000) and run 10000 trials
        const resStd = await fetch(`${srv.baseUrl}/api/kinematic/simulate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 6.0, twd_deg: 180.0 },
            purpose: 'standard',
            trial_count: 10000,
          }),
        })
        expect(resStd.status).toBe(200)
        const bodyStd = (await resStd.json()) as KinematicScenarioV2
        expect(bodyStd.applied_inputs.environment.tws_mps).toBe(6.0)
        expect(bodyStd.applied_inputs.purpose).toBe('standard')
        expect(bodyStd.applied_inputs.trial_count).toBe(10000)
        expect(bodyStd.trial_counts?.scheduled).toBe(10000)
        expect(bodyStd.scenario_id).not.toBe(baseScenario.scenario_id)

        // 3. Fail-closed HTTP 422 checks
        const badPayloads = [
          {
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 8.0, twd_deg: 180.0 },
            purpose: 'preview',
            unexpected_key: 1,
          },
          {
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 8.0, tws_kt: 19.0, twd_deg: 180.0 },
            purpose: 'preview',
          },
          {
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 8.0, twd_deg: 180.0, wind_from_deg: 90.0 },
            purpose: 'preview',
          },
          {
            schema_version: 'ac75-scenario-request-1',
            model_id: 'ac75_wrong_model_id',
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 8.0, twd_deg: 180.0 },
            purpose: 'preview',
          },
          {
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 8.0, twd_deg: 180.0 },
            purpose: 'invalid_mode',
          },
          {
            schema_version: 'ac75-scenario-request-1',
            model_id: modelId,
            team_a: 'ETNZ',
            team_b: 'INEOS',
            course_id: 'barcelona_lvc_4leg',
            environment: { tws_mps: 8.0, twd_deg: 180.0 },
            purpose: 'preview',
            trial_count: 2000,
            n_sims: 5000,
          },
        ]

        for (const badBody of badPayloads) {
          const badRes = await fetch(`${srv.baseUrl}/api/kinematic/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(badBody),
          })
          expect(badRes.status).toBe(422)
        }
      } finally {
        await srv.close()
      }
    })

    it('detects 1-byte tamper in scenarios_catalog.json and returns HTTP 500 on catalog and simulate', async () => {
      const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ac75-tamper-'))
      try {
        const srcForecast = path.join(process.cwd(), '.forecast', 'ac75_learning')
        const ptrRaw = fs.readFileSync(path.join(srcForecast, 'latest_candidate.json'), 'utf-8')
        const ptr = JSON.parse(ptrRaw) as { candidate_id: string; manifest_path: string }

        const dstForecast = path.join(tmpRoot, '.forecast', 'ac75_learning')
        fs.mkdirSync(path.join(dstForecast, 'candidates'), { recursive: true })
        fs.writeFileSync(path.join(dstForecast, 'latest_candidate.json'), ptrRaw)
        fs.cpSync(
          path.join(srcForecast, 'candidates', ptr.candidate_id),
          path.join(dstForecast, 'candidates', ptr.candidate_id),
          { recursive: true }
        )

        // Tamper 1 byte inside scenarios_catalog.json (valid JSON change breaking SHA-256)
        const catFile = path.join(dstForecast, 'candidates', ptr.candidate_id, 'scenarios_catalog.json')
        const catText = fs.readFileSync(catFile, 'utf-8')
        const tampered = catText.replace('"seed": 2027', '"seed": 2028')
        expect(tampered).not.toBe(catText)
        fs.writeFileSync(catFile, tampered, 'utf-8')

        const srv = await startMiddlewareServer(tmpRoot)
        try {
          const catRes = await fetch(`${srv.baseUrl}/api/kinematic/catalog`)
          expect(catRes.status).toBe(500)

          const simRes = await fetch(`${srv.baseUrl}/api/kinematic/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              schema_version: 'ac75-scenario-request-1',
              model_id: ptr.candidate_id,
              team_a: 'ETNZ',
              team_b: 'INEOS',
              course_id: 'barcelona_lvc_4leg',
              environment: { tws_mps: 6.0, twd_deg: 180.0 },
              purpose: 'preview',
            }),
          })
          expect(simRes.status).toBe(500)
        } finally {
          await srv.close()
        }
      } finally {
        fs.rmSync(tmpRoot, { recursive: true, force: true })
      }
    })
  })
})

