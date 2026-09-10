export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  analytics: {
    Tables: {
      batch_metrics_daily: {
        Row: {
          baseline: number
          baseline_scope: string
          batch_code: string
          complete_openings: number
          computed_at: string
          credible_interval_high: number
          credible_interval_low: number
          credible_level: number
          date: string
          first_seen: string
          id: string
          independent_source_count: number
          is_demo: boolean
          last_seen: string
          methodology_version: string
          normalized_batch_code: string
          observed_packs: number
          posterior_mean: number
          probability_above_baseline: number
          probability_above_practical_uplift: number
          product_id: string | null
          region_count: number
          retailer_count: number
          set_id: string
          signal_status: string
        }
        Insert: {
          baseline: number
          baseline_scope: string
          batch_code: string
          complete_openings?: number
          computed_at?: string
          credible_interval_high: number
          credible_interval_low: number
          credible_level?: number
          date: string
          first_seen: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          last_seen: string
          methodology_version: string
          normalized_batch_code: string
          observed_packs?: number
          posterior_mean: number
          probability_above_baseline: number
          probability_above_practical_uplift: number
          product_id?: string | null
          region_count?: number
          retailer_count?: number
          set_id: string
          signal_status: string
        }
        Update: {
          baseline?: number
          baseline_scope?: string
          batch_code?: string
          complete_openings?: number
          computed_at?: string
          credible_interval_high?: number
          credible_interval_low?: number
          credible_level?: number
          date?: string
          first_seen?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          last_seen?: string
          methodology_version?: string
          normalized_batch_code?: string
          observed_packs?: number
          posterior_mean?: number
          probability_above_baseline?: number
          probability_above_practical_uplift?: number
          product_id?: string | null
          region_count?: number
          retailer_count?: number
          set_id?: string
          signal_status?: string
        }
        Relationships: []
      }
      dashboard_daily: {
        Row: {
          accepted_count: number
          accepted_sources: number
          activity_only_count: number
          activity_only_sources: number
          baseline: number | null
          baseline_scope: string
          batch_sightings: number
          build_sha: string
          catalog_version: string
          complete_openings: number
          computed_at: string
          country_code: string
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          data_quality_score: number
          date: string
          delta_from_baseline: number | null
          hit_count: number
          is_demo: boolean
          language: string
          methodology_version: string
          observed_hit_rate: number | null
          observed_packs: number
          posterior_mean: number | null
          rejected_count: number
          rejected_sources: number
          tracked_regions: number
          tracked_retailers: number
          tracked_sets: number
          window_end: string
          window_start: string
        }
        Insert: {
          accepted_count?: number
          accepted_sources?: number
          activity_only_count?: number
          activity_only_sources?: number
          baseline?: number | null
          baseline_scope: string
          batch_sightings?: number
          build_sha: string
          catalog_version: string
          complete_openings?: number
          computed_at?: string
          country_code: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          data_quality_score?: number
          date: string
          delta_from_baseline?: number | null
          hit_count?: number
          is_demo?: boolean
          language?: string
          methodology_version: string
          observed_hit_rate?: number | null
          observed_packs?: number
          posterior_mean?: number | null
          rejected_count?: number
          rejected_sources?: number
          tracked_regions?: number
          tracked_retailers?: number
          tracked_sets?: number
          window_end: string
          window_start: string
        }
        Update: {
          accepted_count?: number
          accepted_sources?: number
          activity_only_count?: number
          activity_only_sources?: number
          baseline?: number | null
          baseline_scope?: string
          batch_sightings?: number
          build_sha?: string
          catalog_version?: string
          complete_openings?: number
          computed_at?: string
          country_code?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          data_quality_score?: number
          date?: string
          delta_from_baseline?: number | null
          hit_count?: number
          is_demo?: boolean
          language?: string
          methodology_version?: string
          observed_hit_rate?: number | null
          observed_packs?: number
          posterior_mean?: number | null
          rejected_count?: number
          rejected_sources?: number
          tracked_regions?: number
          tracked_retailers?: number
          tracked_sets?: number
          window_end?: string
          window_start?: string
        }
        Relationships: []
      }
      region_metrics_daily: {
        Row: {
          accepted_count: number
          activity_only_count: number
          baseline_rates: Json
          baseline_scope: string
          catalog_version: string
          complete_openings: number
          computed_at: string
          credible_intervals: Json
          date: string
          id: string
          independent_source_count: number
          is_demo: boolean
          language: string
          methodology_version: string
          observed_packs: number
          observed_rates: Json
          product_id: string | null
          product_type: string | null
          rarity_counts: Json
          region_id: string
          rejected_count: number
          sample_quality_score: number
          set_id: string | null
          window_end: string
          window_start: string
        }
        Insert: {
          accepted_count?: number
          activity_only_count?: number
          baseline_rates?: Json
          baseline_scope: string
          catalog_version: string
          complete_openings?: number
          computed_at?: string
          credible_intervals?: Json
          date: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version: string
          observed_packs?: number
          observed_rates?: Json
          product_id?: string | null
          product_type?: string | null
          rarity_counts?: Json
          region_id: string
          rejected_count?: number
          sample_quality_score?: number
          set_id?: string | null
          window_end: string
          window_start: string
        }
        Update: {
          accepted_count?: number
          activity_only_count?: number
          baseline_rates?: Json
          baseline_scope?: string
          catalog_version?: string
          complete_openings?: number
          computed_at?: string
          credible_intervals?: Json
          date?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version?: string
          observed_packs?: number
          observed_rates?: Json
          product_id?: string | null
          product_type?: string | null
          rarity_counts?: Json
          region_id?: string
          rejected_count?: number
          sample_quality_score?: number
          set_id?: string | null
          window_end?: string
          window_start?: string
        }
        Relationships: []
      }
      retailer_metrics_daily: {
        Row: {
          accepted_count: number
          activity_only_count: number
          baseline_rates: Json
          baseline_scope: string
          catalog_version: string
          complete_openings: number
          computed_at: string
          credible_intervals: Json
          date: string
          id: string
          independent_source_count: number
          is_demo: boolean
          language: string
          methodology_version: string
          observed_packs: number
          observed_rates: Json
          product_id: string | null
          product_type: string | null
          rarity_counts: Json
          region_id: string | null
          rejected_count: number
          retailer_id: string
          sample_quality_score: number
          set_id: string | null
          window_end: string
          window_start: string
        }
        Insert: {
          accepted_count?: number
          activity_only_count?: number
          baseline_rates?: Json
          baseline_scope: string
          catalog_version: string
          complete_openings?: number
          computed_at?: string
          credible_intervals?: Json
          date: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version: string
          observed_packs?: number
          observed_rates?: Json
          product_id?: string | null
          product_type?: string | null
          rarity_counts?: Json
          region_id?: string | null
          rejected_count?: number
          retailer_id: string
          sample_quality_score?: number
          set_id?: string | null
          window_end: string
          window_start: string
        }
        Update: {
          accepted_count?: number
          activity_only_count?: number
          baseline_rates?: Json
          baseline_scope?: string
          catalog_version?: string
          complete_openings?: number
          computed_at?: string
          credible_intervals?: Json
          date?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version?: string
          observed_packs?: number
          observed_rates?: Json
          product_id?: string | null
          product_type?: string | null
          rarity_counts?: Json
          region_id?: string | null
          rejected_count?: number
          retailer_id?: string
          sample_quality_score?: number
          set_id?: string | null
          window_end?: string
          window_start?: string
        }
        Relationships: []
      }
      reviewed_global_aggregate_audit: {
        Row: {
          aggregate_key: string
          baseline_contract_sha256: string | null
          baseline_id: string | null
          baseline_rate: number | null
          build_sha: string
          calculation_implementation_version: string
          cohort_fingerprint_sha256: string
          complete_openings: number
          country_code: string
          created_at: string
          credible_interval_high: number | null
          credible_interval_low: number | null
          delta_from_baseline: number | null
          id: string
          independent_source_count: number
          language: string
          methodology_version: string
          metric_key: string
          metric_version: string
          observed_packs: number
          observed_rate: number | null
          period_end: string
          period_start: string
          posterior_mean: number | null
          prior_strength: number | null
          probability_above_baseline: number | null
          probability_above_practical: number | null
          product_scope: string
          publication_contract_version: string
          publication_state: string
          qualifying_hit_pack_count: number
          set_scope: string
          signal_status: string | null
          source_domain_set_sha256: string
          withhold_reason: string | null
        }
        Insert: {
          aggregate_key: string
          baseline_contract_sha256?: string | null
          baseline_id?: string | null
          baseline_rate?: number | null
          build_sha: string
          calculation_implementation_version: string
          cohort_fingerprint_sha256: string
          complete_openings: number
          country_code: string
          created_at?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          delta_from_baseline?: number | null
          id?: string
          independent_source_count: number
          language: string
          methodology_version: string
          metric_key: string
          metric_version: string
          observed_packs: number
          observed_rate?: number | null
          period_end: string
          period_start: string
          posterior_mean?: number | null
          prior_strength?: number | null
          probability_above_baseline?: number | null
          probability_above_practical?: number | null
          product_scope: string
          publication_contract_version: string
          publication_state: string
          qualifying_hit_pack_count: number
          set_scope: string
          signal_status?: string | null
          source_domain_set_sha256: string
          withhold_reason?: string | null
        }
        Update: {
          aggregate_key?: string
          baseline_contract_sha256?: string | null
          baseline_id?: string | null
          baseline_rate?: number | null
          build_sha?: string
          calculation_implementation_version?: string
          cohort_fingerprint_sha256?: string
          complete_openings?: number
          country_code?: string
          created_at?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          delta_from_baseline?: number | null
          id?: string
          independent_source_count?: number
          language?: string
          methodology_version?: string
          metric_key?: string
          metric_version?: string
          observed_packs?: number
          observed_rate?: number | null
          period_end?: string
          period_start?: string
          posterior_mean?: number | null
          prior_strength?: number | null
          probability_above_baseline?: number | null
          probability_above_practical?: number | null
          product_scope?: string
          publication_contract_version?: string
          publication_state?: string
          qualifying_hit_pack_count?: number
          set_scope?: string
          signal_status?: string | null
          source_domain_set_sha256?: string
          withhold_reason?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "reviewed_global_aggregate_audit_baseline_id_fkey"
            columns: ["baseline_id"]
            isOneToOne: false
            referencedRelation: "reviewed_global_aggregate_baselines"
            referencedColumns: ["baseline_id"]
          },
        ]
      }
      reviewed_global_aggregate_authorized_source_bindings: {
        Row: {
          authorization_contract_sha256: string
          authorization_contract_version: string
          authorization_reference_sha256: string
          binding_key: string
          created_at: string
          independent_source_key: string
          source_identity_sha256: string
          valid_from: string
          valid_until: string | null
        }
        Insert: {
          authorization_contract_sha256: string
          authorization_contract_version: string
          authorization_reference_sha256: string
          binding_key: string
          created_at?: string
          independent_source_key: string
          source_identity_sha256: string
          valid_from: string
          valid_until?: string | null
        }
        Update: {
          authorization_contract_sha256?: string
          authorization_contract_version?: string
          authorization_reference_sha256?: string
          binding_key?: string
          created_at?: string
          independent_source_key?: string
          source_identity_sha256?: string
          valid_from?: string
          valid_until?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "rga_asb_source_key_fkey"
            columns: ["independent_source_key"]
            isOneToOne: false
            referencedRelation: "reviewed_global_aggregate_independent_sources"
            referencedColumns: ["source_key"]
          },
        ]
      }
      reviewed_global_aggregate_baselines: {
        Row: {
          baseline_id: string
          baseline_rate: number
          baseline_version: string
          contract_sha256: string
          created_at: string
          language: string
          metric_key: string
          metric_version: string
          product_scope: string
          provenance_sha256: string
          set_external_id: string
          valid_from: string
          valid_to: string | null
        }
        Insert: {
          baseline_id: string
          baseline_rate: number
          baseline_version: string
          contract_sha256: string
          created_at?: string
          language: string
          metric_key: string
          metric_version: string
          product_scope?: string
          provenance_sha256: string
          set_external_id: string
          valid_from: string
          valid_to?: string | null
        }
        Update: {
          baseline_id?: string
          baseline_rate?: number
          baseline_version?: string
          contract_sha256?: string
          created_at?: string
          language?: string
          metric_key?: string
          metric_version?: string
          product_scope?: string
          provenance_sha256?: string
          set_external_id?: string
          valid_from?: string
          valid_to?: string | null
        }
        Relationships: []
      }
      reviewed_global_aggregate_independent_sources: {
        Row: {
          canonical_domain: string
          created_at: string
          domain_contract_sha256: string
          domain_contract_version: string
          source_key: string
        }
        Insert: {
          canonical_domain: string
          created_at?: string
          domain_contract_sha256: string
          domain_contract_version: string
          source_key: string
        }
        Update: {
          canonical_domain?: string
          created_at?: string
          domain_contract_sha256?: string
          domain_contract_version?: string
          source_key?: string
        }
        Relationships: []
      }
      reviewed_global_aggregate_input_admissions: {
        Row: {
          accepted_observation_id: string | null
          admission_contract_sha256: string
          admission_contract_version: string
          admission_key: string
          admitted_at: string
          binding_key: string | null
          canonical_opening_fingerprint_sha256: string
          input_kind: string
          public_study_key: string | null
        }
        Insert: {
          accepted_observation_id?: string | null
          admission_contract_sha256: string
          admission_contract_version: string
          admission_key: string
          admitted_at?: string
          binding_key?: string | null
          canonical_opening_fingerprint_sha256: string
          input_kind: string
          public_study_key?: string | null
        }
        Update: {
          accepted_observation_id?: string | null
          admission_contract_sha256?: string
          admission_contract_version?: string
          admission_key?: string
          admitted_at?: string
          binding_key?: string | null
          canonical_opening_fingerprint_sha256?: string
          input_kind?: string
          public_study_key?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "rga_ia_binding_key_fkey"
            columns: ["binding_key"]
            isOneToOne: false
            referencedRelation: "reviewed_global_aggregate_authorized_source_bindings"
            referencedColumns: ["binding_key"]
          },
        ]
      }
      set_metrics_daily: {
        Row: {
          accepted_count: number
          activity_only_count: number
          baseline_rates: Json
          baseline_scope: string
          catalog_version: string
          complete_openings: number
          computed_at: string
          credible_intervals: Json
          date: string
          id: string
          independent_source_count: number
          is_demo: boolean
          language: string
          methodology_version: string
          observed_packs: number
          observed_rates: Json
          product_type: string | null
          rarity_counts: Json
          rejected_count: number
          sample_quality_score: number
          set_id: string
          window_end: string
          window_start: string
        }
        Insert: {
          accepted_count?: number
          activity_only_count?: number
          baseline_rates?: Json
          baseline_scope: string
          catalog_version: string
          complete_openings?: number
          computed_at?: string
          credible_intervals?: Json
          date: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version: string
          observed_packs?: number
          observed_rates?: Json
          product_type?: string | null
          rarity_counts?: Json
          rejected_count?: number
          sample_quality_score?: number
          set_id: string
          window_end: string
          window_start: string
        }
        Update: {
          accepted_count?: number
          activity_only_count?: number
          baseline_rates?: Json
          baseline_scope?: string
          catalog_version?: string
          complete_openings?: number
          computed_at?: string
          credible_intervals?: Json
          date?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version?: string
          observed_packs?: number
          observed_rates?: Json
          product_type?: string | null
          rarity_counts?: Json
          rejected_count?: number
          sample_quality_score?: number
          set_id?: string
          window_end?: string
          window_start?: string
        }
        Relationships: []
      }
      signals: {
        Row: {
          baseline: number | null
          baseline_scope: string
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          entity_key: string
          entity_type: string
          evidence_tier: string
          expires_at: string
          explanation: Json
          first_detected_at: string
          id: string
          independent_source_count: number
          is_demo: boolean
          is_public: boolean
          last_updated_at: string
          methodology_version: string
          metric: string
          observed: number | null
          posterior_mean: number | null
          probability_above_baseline: number | null
          probability_above_practical_uplift: number | null
          sample_size: number
          set_id: string | null
          signal_type: string
          status: string
        }
        Insert: {
          baseline?: number | null
          baseline_scope: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          entity_key: string
          entity_type: string
          evidence_tier: string
          expires_at: string
          explanation: Json
          first_detected_at: string
          id?: string
          independent_source_count: number
          is_demo?: boolean
          is_public?: boolean
          last_updated_at: string
          methodology_version: string
          metric: string
          observed?: number | null
          posterior_mean?: number | null
          probability_above_baseline?: number | null
          probability_above_practical_uplift?: number | null
          sample_size: number
          set_id?: string | null
          signal_type: string
          status: string
        }
        Update: {
          baseline?: number | null
          baseline_scope?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          entity_key?: string
          entity_type?: string
          evidence_tier?: string
          expires_at?: string
          explanation?: Json
          first_detected_at?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          is_public?: boolean
          last_updated_at?: string
          methodology_version?: string
          metric?: string
          observed?: number | null
          posterior_mean?: number | null
          probability_above_baseline?: number | null
          probability_above_practical_uplift?: number | null
          sample_size?: number
          set_id?: string | null
          signal_type?: string
          status?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      reviewed_global_aggregate_cohort_v1: {
        Args: { p_as_of: string; p_period_end: string; p_period_start: string }
        Returns: {
          country_code: string
          country_name: string
          independent_source_key: string
          input_id: string
          input_kind: string
          language: string
          methodology_version: string
          observed_at: string
          pack_count: number
          product_scope: string
          qualifying_hit_pack_count: number
          set_external_id: string
          source_contract_version: string
        }[]
      }
      reviewed_global_beta_parameters_v1: {
        Args: {
          p_baseline_rate: number
          p_hits: number
          p_packs: number
          p_prior_strength?: number
        }
        Returns: {
          alpha: number
          beta: number
          posterior_mean: number
        }[]
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  catalog: {
    Tables: {
      cards: {
        Row: {
          collector_number: string | null
          created_at: string
          external_id: string
          external_source: string
          id: string
          is_demo: boolean
          language: string
          metadata: Json
          name: string
          rarity: string | null
          set_id: string
          updated_at: string
        }
        Insert: {
          collector_number?: string | null
          created_at?: string
          external_id: string
          external_source: string
          id?: string
          is_demo?: boolean
          language?: string
          metadata?: Json
          name: string
          rarity?: string | null
          set_id: string
          updated_at?: string
        }
        Update: {
          collector_number?: string | null
          created_at?: string
          external_id?: string
          external_source?: string
          id?: string
          is_demo?: boolean
          language?: string
          metadata?: Json
          name?: string
          rarity?: string | null
          set_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "cards_set_id_fkey"
            columns: ["set_id"]
            isOneToOne: false
            referencedRelation: "sets"
            referencedColumns: ["id"]
          },
        ]
      }
      iso_alpha2_codes: {
        Row: {
          code: string
          country_name: string
        }
        Insert: {
          code: string
          country_name: string
        }
        Update: {
          code?: string
          country_name?: string
        }
        Relationships: []
      }
      products: {
        Row: {
          created_at: string
          declared_pack_count: number | null
          ean: string | null
          id: string
          is_active: boolean
          is_demo: boolean
          language: string
          metadata: Json
          name: string
          product_type: string
          set_id: string | null
          sku: string | null
          slug: string
          upc: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          declared_pack_count?: number | null
          ean?: string | null
          id?: string
          is_active?: boolean
          is_demo?: boolean
          language?: string
          metadata?: Json
          name: string
          product_type: string
          set_id?: string | null
          sku?: string | null
          slug: string
          upc?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          declared_pack_count?: number | null
          ean?: string | null
          id?: string
          is_active?: boolean
          is_demo?: boolean
          language?: string
          metadata?: Json
          name?: string
          product_type?: string
          set_id?: string | null
          sku?: string | null
          slug?: string
          upc?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "products_set_id_fkey"
            columns: ["set_id"]
            isOneToOne: false
            referencedRelation: "sets"
            referencedColumns: ["id"]
          },
        ]
      }
      regions: {
        Row: {
          city: string | null
          country_code: string
          created_at: string
          id: string
          is_demo: boolean
          latitude: number | null
          longitude: number | null
          metadata: Json
          name: string
          parent_id: string | null
          region_type: string
          slug: string
          state_code: string | null
          updated_at: string
        }
        Insert: {
          city?: string | null
          country_code: string
          created_at?: string
          id?: string
          is_demo?: boolean
          latitude?: number | null
          longitude?: number | null
          metadata?: Json
          name: string
          parent_id?: string | null
          region_type: string
          slug: string
          state_code?: string | null
          updated_at?: string
        }
        Update: {
          city?: string | null
          country_code?: string
          created_at?: string
          id?: string
          is_demo?: boolean
          latitude?: number | null
          longitude?: number | null
          metadata?: Json
          name?: string
          parent_id?: string | null
          region_type?: string
          slug?: string
          state_code?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "regions_parent_id_fkey"
            columns: ["parent_id"]
            isOneToOne: false
            referencedRelation: "regions"
            referencedColumns: ["id"]
          },
        ]
      }
      retailers: {
        Row: {
          country_code: string | null
          created_at: string
          id: string
          is_demo: boolean
          metadata: Json
          name: string
          slug: string
          updated_at: string
          website_domain: string | null
        }
        Insert: {
          country_code?: string | null
          created_at?: string
          id?: string
          is_demo?: boolean
          metadata?: Json
          name: string
          slug: string
          updated_at?: string
          website_domain?: string | null
        }
        Update: {
          country_code?: string | null
          created_at?: string
          id?: string
          is_demo?: boolean
          metadata?: Json
          name?: string
          slug?: string
          updated_at?: string
          website_domain?: string | null
        }
        Relationships: []
      }
      sets: {
        Row: {
          created_at: string
          external_id: string
          external_source: string
          id: string
          is_active: boolean
          is_demo: boolean
          language: string
          metadata: Json
          name: string
          rarity_taxonomy: Json
          release_date: string | null
          series_name: string | null
          set_code: string | null
          slug: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          external_id: string
          external_source: string
          id?: string
          is_active?: boolean
          is_demo?: boolean
          language?: string
          metadata?: Json
          name: string
          rarity_taxonomy?: Json
          release_date?: string | null
          series_name?: string | null
          set_code?: string | null
          slug: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          external_id?: string
          external_source?: string
          id?: string
          is_active?: boolean
          is_demo?: boolean
          language?: string
          metadata?: Json
          name?: string
          rarity_taxonomy?: Json
          release_date?: string | null
          series_name?: string | null
          set_code?: string | null
          slug?: string
          updated_at?: string
        }
        Relationships: []
      }
      stores: {
        Row: {
          created_at: string
          id: string
          is_demo: boolean
          latitude: number | null
          longitude: number | null
          metadata: Json
          name: string
          public_address: string | null
          region_id: string | null
          retailer_id: string
          slug: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: string
          is_demo?: boolean
          latitude?: number | null
          longitude?: number | null
          metadata?: Json
          name: string
          public_address?: string | null
          region_id?: string | null
          retailer_id: string
          slug: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: string
          is_demo?: boolean
          latitude?: number | null
          longitude?: number | null
          metadata?: Json
          name?: string
          public_address?: string | null
          region_id?: string | null
          retailer_id?: string
          slug?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "stores_region_id_fkey"
            columns: ["region_id"]
            isOneToOne: false
            referencedRelation: "regions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "stores_retailer_id_fkey"
            columns: ["retailer_id"]
            isOneToOne: false
            referencedRelation: "retailers"
            referencedColumns: ["id"]
          },
        ]
      }
      sync_state: {
        Row: {
          content_sha256: string
          etag: string | null
          is_demo: boolean
          item_count: number
          language: string
          last_changed_at: string
          last_checked_at: string
          last_job_id: string | null
          revision: number
          scope: string
          source: string
        }
        Insert: {
          content_sha256: string
          etag?: string | null
          is_demo?: boolean
          item_count: number
          language: string
          last_changed_at: string
          last_checked_at: string
          last_job_id?: string | null
          revision?: number
          scope: string
          source: string
        }
        Update: {
          content_sha256?: string
          etag?: string | null
          is_demo?: boolean
          item_count?: number
          language?: string
          last_changed_at?: string
          last_checked_at?: string
          last_job_id?: string | null
          revision?: number
          scope?: string
          source?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  ingest: {
    Tables: {
      admin_audit_log: {
        Row: {
          action: string
          actor_email_hash: string | null
          actor_id: string | null
          created_at: string
          detail: Json
          id: string
          ip_hash: string | null
          is_demo: boolean
          object_id: string | null
          object_type: string
          occurred_at: string
          retention_until: string
        }
        Insert: {
          action: string
          actor_email_hash?: string | null
          actor_id?: string | null
          created_at?: string
          detail?: Json
          id?: string
          ip_hash?: string | null
          is_demo?: boolean
          object_id?: string | null
          object_type: string
          occurred_at?: string
          retention_until?: string
        }
        Update: {
          action?: string
          actor_email_hash?: string | null
          actor_id?: string | null
          created_at?: string
          detail?: Json
          id?: string
          ip_hash?: string | null
          is_demo?: boolean
          object_id?: string | null
          object_type?: string
          occurred_at?: string
          retention_until?: string
        }
        Relationships: []
      }
      ai_usage_daily: {
        Row: {
          date: string
          estimated_cost_aud: number
          input_tokens: number
          is_demo: boolean
          model: string
          output_tokens: number
          provider: string
          request_count: number
          stage: string
        }
        Insert: {
          date: string
          estimated_cost_aud?: number
          input_tokens?: number
          is_demo?: boolean
          model: string
          output_tokens?: number
          provider: string
          request_count?: number
          stage: string
        }
        Update: {
          date?: string
          estimated_cost_aud?: number
          input_tokens?: number
          is_demo?: boolean
          model?: string
          output_tokens?: number
          provider?: string
          request_count?: number
          stage?: string
        }
        Relationships: []
      }
      authorized_opening_observations: {
        Row: {
          accepted_at: string
          authorization_reference_sha256: string
          country_code: string
          country_name: string
          denominator_complete: boolean
          discovery_candidate_sha256: string | null
          discovery_platform: string | null
          evidence_sha256: string
          geography_basis: string
          geography_confidence: string
          id: string
          language: string
          methodology_version: string
          observed_at: string
          pack_count: number
          product_scope: string
          provenance_dedupe_sha256: string
          qualifying_hit_pack_count: number
          source_identity_sha256: string
          statistics_eligible: boolean
          submission_id: string
          submission_key: string
          tcgdex_set_id: string
        }
        Insert: {
          accepted_at?: string
          authorization_reference_sha256: string
          country_code: string
          country_name: string
          denominator_complete: boolean
          discovery_candidate_sha256?: string | null
          discovery_platform?: string | null
          evidence_sha256: string
          geography_basis: string
          geography_confidence: string
          id?: string
          language: string
          methodology_version?: string
          observed_at: string
          pack_count: number
          product_scope: string
          provenance_dedupe_sha256: string
          qualifying_hit_pack_count: number
          source_identity_sha256: string
          statistics_eligible: boolean
          submission_id: string
          submission_key: string
          tcgdex_set_id: string
        }
        Update: {
          accepted_at?: string
          authorization_reference_sha256?: string
          country_code?: string
          country_name?: string
          denominator_complete?: boolean
          discovery_candidate_sha256?: string | null
          discovery_platform?: string | null
          evidence_sha256?: string
          geography_basis?: string
          geography_confidence?: string
          id?: string
          language?: string
          methodology_version?: string
          observed_at?: string
          pack_count?: number
          product_scope?: string
          provenance_dedupe_sha256?: string
          qualifying_hit_pack_count?: number
          source_identity_sha256?: string
          statistics_eligible?: boolean
          submission_id?: string
          submission_key?: string
          tcgdex_set_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "authorized_opening_observations_submission_id_fkey"
            columns: ["submission_id"]
            isOneToOne: true
            referencedRelation: "authorized_opening_submissions"
            referencedColumns: ["id"]
          },
        ]
      }
      authorized_opening_retractions: {
        Row: {
          accepted_observation_id: string
          id: string
          reason_code: string
          retracted_at: string
          reviewer_reference_sha256: string
        }
        Insert: {
          accepted_observation_id: string
          id?: string
          reason_code: string
          retracted_at?: string
          reviewer_reference_sha256: string
        }
        Update: {
          accepted_observation_id?: string
          id?: string
          reason_code?: string
          retracted_at?: string
          reviewer_reference_sha256?: string
        }
        Relationships: [
          {
            foreignKeyName: "authorized_opening_retractions_accepted_observation_id_fkey"
            columns: ["accepted_observation_id"]
            isOneToOne: true
            referencedRelation: "authorized_opening_observations"
            referencedColumns: ["id"]
          },
        ]
      }
      authorized_opening_review_events: {
        Row: {
          from_state: string | null
          id: string
          reason_code: string
          reviewed_at: string
          reviewer_reference_sha256: string | null
          revision: number
          submission_id: string
          to_state: string
        }
        Insert: {
          from_state?: string | null
          id?: string
          reason_code: string
          reviewed_at?: string
          reviewer_reference_sha256?: string | null
          revision: number
          submission_id: string
          to_state: string
        }
        Update: {
          from_state?: string | null
          id?: string
          reason_code?: string
          reviewed_at?: string
          reviewer_reference_sha256?: string | null
          revision?: number
          submission_id?: string
          to_state?: string
        }
        Relationships: [
          {
            foreignKeyName: "authorized_opening_review_events_submission_id_fkey"
            columns: ["submission_id"]
            isOneToOne: false
            referencedRelation: "authorized_opening_submissions"
            referencedColumns: ["id"]
          },
        ]
      }
      authorized_opening_submissions: {
        Row: {
          authorization_reference_sha256: string
          country_code: string
          country_name: string
          created_at: string
          denominator_complete: boolean
          discovery_candidate_sha256: string | null
          discovery_platform: string | null
          evidence_sha256: string
          expires_at: string
          geography_basis: string
          geography_confidence: string
          id: string
          language: string
          observed_at: string
          pack_count: number
          product_scope: string
          provenance_dedupe_sha256: string
          qualifying_hit_pack_count: number
          revision: number
          source_identity_sha256: string
          state: string
          statistics_eligible_requested: boolean
          submission_key: string
          tcgdex_set_id: string
          updated_at: string
        }
        Insert: {
          authorization_reference_sha256: string
          country_code: string
          country_name: string
          created_at?: string
          denominator_complete: boolean
          discovery_candidate_sha256?: string | null
          discovery_platform?: string | null
          evidence_sha256: string
          expires_at?: string
          geography_basis: string
          geography_confidence: string
          id?: string
          language: string
          observed_at: string
          pack_count: number
          product_scope: string
          provenance_dedupe_sha256: string
          qualifying_hit_pack_count: number
          revision?: number
          source_identity_sha256: string
          state?: string
          statistics_eligible_requested: boolean
          submission_key: string
          tcgdex_set_id: string
          updated_at?: string
        }
        Update: {
          authorization_reference_sha256?: string
          country_code?: string
          country_name?: string
          created_at?: string
          denominator_complete?: boolean
          discovery_candidate_sha256?: string | null
          discovery_platform?: string | null
          evidence_sha256?: string
          expires_at?: string
          geography_basis?: string
          geography_confidence?: string
          id?: string
          language?: string
          observed_at?: string
          pack_count?: number
          product_scope?: string
          provenance_dedupe_sha256?: string
          qualifying_hit_pack_count?: number
          revision?: number
          source_identity_sha256?: string
          state?: string
          statistics_eligible_requested?: boolean
          submission_key?: string
          tcgdex_set_id?: string
          updated_at?: string
        }
        Relationships: []
      }
      batch_sightings: {
        Row: {
          activity_only: boolean
          batch_code: string
          confidence: number
          created_at: string
          expires_at: string
          id: string
          is_demo: boolean
          lot_code: string | null
          normalized_batch_code: string
          normalized_lot_code: string | null
          observed_at: string
          opening_id: string | null
          pack_quantity: number | null
          product_id: string | null
          region_id: string | null
          retailer_id: string | null
          set_id: string | null
          source_item_id: string
          store_id: string | null
        }
        Insert: {
          activity_only?: boolean
          batch_code: string
          confidence: number
          created_at?: string
          expires_at?: string
          id?: string
          is_demo?: boolean
          lot_code?: string | null
          normalized_batch_code: string
          normalized_lot_code?: string | null
          observed_at?: string
          opening_id?: string | null
          pack_quantity?: number | null
          product_id?: string | null
          region_id?: string | null
          retailer_id?: string | null
          set_id?: string | null
          source_item_id: string
          store_id?: string | null
        }
        Update: {
          activity_only?: boolean
          batch_code?: string
          confidence?: number
          created_at?: string
          expires_at?: string
          id?: string
          is_demo?: boolean
          lot_code?: string | null
          normalized_batch_code?: string
          normalized_lot_code?: string | null
          observed_at?: string
          opening_id?: string | null
          pack_quantity?: number | null
          product_id?: string | null
          region_id?: string | null
          retailer_id?: string | null
          set_id?: string | null
          source_item_id?: string
          store_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "batch_sightings_opening_id_fkey"
            columns: ["opening_id"]
            isOneToOne: false
            referencedRelation: "openings"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "batch_sightings_source_item_id_fkey"
            columns: ["source_item_id"]
            isOneToOne: false
            referencedRelation: "source_items"
            referencedColumns: ["id"]
          },
        ]
      }
      bluesky_jetstream_candidates: {
        Row: {
          at_uri: string
          collector_version: string
          created_at: string
          deleted_at: string | null
          expires_at: string
          first_seen_at: string
          is_demo: boolean
          last_cursor: number
          last_seen_at: string
          public_url: string
          published_at: string | null
          record_sha256: string
          source_policy_id: string
          source_policy_version: string
          text_excerpt: string | null
          updated_at: string
        }
        Insert: {
          at_uri: string
          collector_version: string
          created_at?: string
          deleted_at?: string | null
          expires_at: string
          first_seen_at: string
          is_demo?: boolean
          last_cursor: number
          last_seen_at: string
          public_url: string
          published_at?: string | null
          record_sha256: string
          source_policy_id: string
          source_policy_version: string
          text_excerpt?: string | null
          updated_at?: string
        }
        Update: {
          at_uri?: string
          collector_version?: string
          created_at?: string
          deleted_at?: string | null
          expires_at?: string
          first_seen_at?: string
          is_demo?: boolean
          last_cursor?: number
          last_seen_at?: string
          public_url?: string
          published_at?: string | null
          record_sha256?: string
          source_policy_id?: string
          source_policy_version?: string
          text_excerpt?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "bluesky_jetstream_candidates_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      bluesky_jetstream_checkpoints: {
        Row: {
          bytes_seen_total: number
          candidates_seen_total: number
          collection: string
          created_at: string
          deletions_seen_total: number
          endpoint: string
          events_seen_total: number
          is_demo: boolean
          last_collected_at: string | null
          last_cursor: number | null
          protocol: string
          source_policy_id: string
          updated_at: string
        }
        Insert: {
          bytes_seen_total?: number
          candidates_seen_total?: number
          collection: string
          created_at?: string
          deletions_seen_total?: number
          endpoint: string
          events_seen_total?: number
          is_demo?: boolean
          last_collected_at?: string | null
          last_cursor?: number | null
          protocol: string
          source_policy_id: string
          updated_at?: string
        }
        Update: {
          bytes_seen_total?: number
          candidates_seen_total?: number
          collection?: string
          created_at?: string
          deletions_seen_total?: number
          endpoint?: string
          events_seen_total?: number
          is_demo?: boolean
          last_collected_at?: string | null
          last_cursor?: number | null
          protocol?: string
          source_policy_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "bluesky_jetstream_checkpoints_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: true
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      bluesky_jetstream_observations: {
        Row: {
          at_uri: string
          cursor: number
          expires_at: string
          id: number
          is_demo: boolean
          observed_at: string
          operation: string
          public_url: string | null
          published_at: string | null
          record_sha256: string | null
          source_policy_id: string
          text_excerpt: string | null
        }
        Insert: {
          at_uri: string
          cursor: number
          expires_at: string
          id?: never
          is_demo?: boolean
          observed_at: string
          operation: string
          public_url?: string | null
          published_at?: string | null
          record_sha256?: string | null
          source_policy_id: string
          text_excerpt?: string | null
        }
        Update: {
          at_uri?: string
          cursor?: number
          expires_at?: string
          id?: never
          is_demo?: boolean
          observed_at?: string
          operation?: string
          public_url?: string | null
          published_at?: string | null
          record_sha256?: string | null
          source_policy_id?: string
          text_excerpt?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "bluesky_jetstream_observations_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      browser_sessions: {
        Row: {
          authenticated_sources: Json
          daemon_connected: boolean
          extension_connected: boolean
          is_demo: boolean
          last_check_at: string
          last_error: string | null
          last_successful_command_at: string | null
          profile_name: string
          status: string
        }
        Insert: {
          authenticated_sources?: Json
          daemon_connected?: boolean
          extension_connected?: boolean
          is_demo?: boolean
          last_check_at?: string
          last_error?: string | null
          last_successful_command_at?: string | null
          profile_name: string
          status?: string
        }
        Update: {
          authenticated_sources?: Json
          daemon_connected?: boolean
          extension_connected?: boolean
          is_demo?: boolean
          last_check_at?: string
          last_error?: string | null
          last_successful_command_at?: string | null
          profile_name?: string
          status?: string
        }
        Relationships: []
      }
      extraction_runs: {
        Row: {
          completed_at: string | null
          confidence: number | null
          created_at: string
          decision: string | null
          error_code: string | null
          error_message: string | null
          estimated_cost_aud: number
          expires_at: string
          id: string
          input_hash: string
          input_tokens: number
          is_demo: boolean
          latency_ms: number | null
          model: string
          output_json: Json | null
          output_tokens: number
          prompt_version: string
          provider: string
          source_item_id: string
          stage: string
          started_at: string
          updated_at: string
        }
        Insert: {
          completed_at?: string | null
          confidence?: number | null
          created_at?: string
          decision?: string | null
          error_code?: string | null
          error_message?: string | null
          estimated_cost_aud?: number
          expires_at?: string
          id?: string
          input_hash: string
          input_tokens?: number
          is_demo?: boolean
          latency_ms?: number | null
          model: string
          output_json?: Json | null
          output_tokens?: number
          prompt_version: string
          provider: string
          source_item_id: string
          stage: string
          started_at?: string
          updated_at?: string
        }
        Update: {
          completed_at?: string | null
          confidence?: number | null
          created_at?: string
          decision?: string | null
          error_code?: string | null
          error_message?: string | null
          estimated_cost_aud?: number
          expires_at?: string
          id?: string
          input_hash?: string
          input_tokens?: number
          is_demo?: boolean
          latency_ms?: number | null
          model?: string
          output_json?: Json | null
          output_tokens?: number
          prompt_version?: string
          provider?: string
          source_item_id?: string
          stage?: string
          started_at?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "extraction_runs_source_item_id_fkey"
            columns: ["source_item_id"]
            isOneToOne: false
            referencedRelation: "source_items"
            referencedColumns: ["id"]
          },
        ]
      }
      jobs: {
        Row: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }
        Insert: {
          attempts?: number
          available_at?: string
          completed_at?: string | null
          created_at?: string
          dedupe_key?: string | null
          id?: string
          is_demo?: boolean
          job_type: string
          last_error_code?: string | null
          last_error_message?: string | null
          lease_generation?: number
          lock_expires_at?: string | null
          locked_at?: string | null
          locked_by?: string | null
          max_attempts?: number
          payload?: Json
          priority?: number
          retention_until?: string
          status?: string
          updated_at?: string
        }
        Update: {
          attempts?: number
          available_at?: string
          completed_at?: string | null
          created_at?: string
          dedupe_key?: string | null
          id?: string
          is_demo?: boolean
          job_type?: string
          last_error_code?: string | null
          last_error_message?: string | null
          lease_generation?: number
          lock_expires_at?: string | null
          locked_at?: string | null
          locked_by?: string | null
          max_attempts?: number
          payload?: Json
          priority?: number
          retention_until?: string
          status?: string
          updated_at?: string
        }
        Relationships: []
      }
      mastodon_public_hashtag_candidates: {
        Row: {
          activity_only: boolean
          created_at: string
          expires_at: string
          first_seen_at: string
          is_demo: boolean
          last_seen_at: string
          matched_tags: string[]
          published_at: string
          source_policy_id: string
          statistics_eligible: boolean
          status_key_sha256: string
          updated_at: string
        }
        Insert: {
          activity_only?: boolean
          created_at?: string
          expires_at: string
          first_seen_at: string
          is_demo?: boolean
          last_seen_at: string
          matched_tags: string[]
          published_at: string
          source_policy_id: string
          statistics_eligible?: boolean
          status_key_sha256: string
          updated_at?: string
        }
        Update: {
          activity_only?: boolean
          created_at?: string
          expires_at?: string
          first_seen_at?: string
          is_demo?: boolean
          last_seen_at?: string
          matched_tags?: string[]
          published_at?: string
          source_policy_id?: string
          statistics_eligible?: boolean
          status_key_sha256?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "mastodon_public_hashtag_candidates_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      mastodon_public_hashtag_checkpoints: {
        Row: {
          bytes_seen_total: number
          candidates_seen_total: number
          created_at: string
          incomplete: boolean
          instance_key: string
          is_demo: boolean
          last_collected_at: string | null
          last_status_id: string | null
          requests_seen_total: number
          source_policy_id: string
          statuses_seen_total: number
          tag_key: string
          updated_at: string
        }
        Insert: {
          bytes_seen_total?: number
          candidates_seen_total?: number
          created_at?: string
          incomplete?: boolean
          instance_key: string
          is_demo?: boolean
          last_collected_at?: string | null
          last_status_id?: string | null
          requests_seen_total?: number
          source_policy_id: string
          statuses_seen_total?: number
          tag_key: string
          updated_at?: string
        }
        Update: {
          bytes_seen_total?: number
          candidates_seen_total?: number
          created_at?: string
          incomplete?: boolean
          instance_key?: string
          is_demo?: boolean
          last_collected_at?: string | null
          last_status_id?: string | null
          requests_seen_total?: number
          source_policy_id?: string
          statuses_seen_total?: number
          tag_key?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "mastodon_public_hashtag_checkpoints_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      mastodon_public_hashtag_observations: {
        Row: {
          activity_only: boolean
          expires_at: string
          is_demo: boolean
          matched_tags: string[]
          observed_at: string
          published_at: string
          source_policy_id: string
          statistics_eligible: boolean
          status_key_sha256: string
          tag_key: string
        }
        Insert: {
          activity_only?: boolean
          expires_at: string
          is_demo?: boolean
          matched_tags: string[]
          observed_at: string
          published_at: string
          source_policy_id: string
          statistics_eligible?: boolean
          status_key_sha256: string
          tag_key: string
        }
        Update: {
          activity_only?: boolean
          expires_at?: string
          is_demo?: boolean
          matched_tags?: string[]
          observed_at?: string
          published_at?: string
          source_policy_id?: string
          statistics_eligible?: boolean
          status_key_sha256?: string
          tag_key?: string
        }
        Relationships: [
          {
            foreignKeyName: "mastodon_public_hashtag_observations_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      mastodon_rate_cooldowns: {
        Row: {
          cooldown_until: string
          created_at: string
          instance_key: string
          is_demo: boolean
          source_policy_id: string
          updated_at: string
        }
        Insert: {
          cooldown_until?: string
          created_at?: string
          instance_key: string
          is_demo?: boolean
          source_policy_id: string
          updated_at?: string
        }
        Update: {
          cooldown_until?: string
          created_at?: string
          instance_key?: string
          is_demo?: boolean
          source_policy_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "mastodon_rate_cooldowns_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: true
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      nostr_relay_candidates: {
        Row: {
          activity_only: boolean
          author_sha256: string
          content_sha256: string
          created_at: string
          deleted_at: string | null
          event_id: string
          expires_at: string
          first_seen_at: string
          is_demo: boolean
          last_seen_at: string
          matched_tags: string[]
          published_at: string
          relay_key: string
          source_policy_id: string
          statistics_eligible: boolean
          updated_at: string
        }
        Insert: {
          activity_only?: boolean
          author_sha256: string
          content_sha256: string
          created_at?: string
          deleted_at?: string | null
          event_id: string
          expires_at: string
          first_seen_at: string
          is_demo?: boolean
          last_seen_at: string
          matched_tags: string[]
          published_at: string
          relay_key: string
          source_policy_id: string
          statistics_eligible?: boolean
          updated_at?: string
        }
        Update: {
          activity_only?: boolean
          author_sha256?: string
          content_sha256?: string
          created_at?: string
          deleted_at?: string | null
          event_id?: string
          expires_at?: string
          first_seen_at?: string
          is_demo?: boolean
          last_seen_at?: string
          matched_tags?: string[]
          published_at?: string
          relay_key?: string
          source_policy_id?: string
          statistics_eligible?: boolean
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "nostr_relay_candidates_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      nostr_relay_checkpoints: {
        Row: {
          approved_tags: string[]
          bytes_seen_total: number
          candidates_seen_total: number
          created_at: string
          deletions_seen_total: number
          endpoint: string
          events_seen_total: number
          is_demo: boolean
          last_checkpoint: string | null
          nip11_url: string
          protocol: string
          relay_key: string
          source_policy_id: string
          updated_at: string
        }
        Insert: {
          approved_tags: string[]
          bytes_seen_total?: number
          candidates_seen_total?: number
          created_at?: string
          deletions_seen_total?: number
          endpoint: string
          events_seen_total?: number
          is_demo?: boolean
          last_checkpoint?: string | null
          nip11_url: string
          protocol: string
          relay_key: string
          source_policy_id: string
          updated_at?: string
        }
        Update: {
          approved_tags?: string[]
          bytes_seen_total?: number
          candidates_seen_total?: number
          created_at?: string
          deletions_seen_total?: number
          endpoint?: string
          events_seen_total?: number
          is_demo?: boolean
          last_checkpoint?: string | null
          nip11_url?: string
          protocol?: string
          relay_key?: string
          source_policy_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "nostr_relay_checkpoints_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: true
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      nostr_relay_observations: {
        Row: {
          activity_only: boolean
          author_sha256: string
          content_sha256: string | null
          event_id: string
          expires_at: string
          id: number
          is_demo: boolean
          matched_tags: string[] | null
          observed_at: string
          operation: string
          published_at: string
          relay_key: string
          source_policy_id: string
          statistics_eligible: boolean
          target_event_ids: string[]
        }
        Insert: {
          activity_only?: boolean
          author_sha256: string
          content_sha256?: string | null
          event_id: string
          expires_at: string
          id?: never
          is_demo?: boolean
          matched_tags?: string[] | null
          observed_at: string
          operation: string
          published_at: string
          relay_key: string
          source_policy_id: string
          statistics_eligible?: boolean
          target_event_ids?: string[]
        }
        Update: {
          activity_only?: boolean
          author_sha256?: string
          content_sha256?: string | null
          event_id?: string
          expires_at?: string
          id?: never
          is_demo?: boolean
          matched_tags?: string[] | null
          observed_at?: string
          operation?: string
          published_at?: string
          relay_key?: string
          source_policy_id?: string
          statistics_eligible?: boolean
          target_event_ids?: string[]
        }
        Relationships: [
          {
            foreignKeyName: "nostr_relay_observations_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      numbered_family_admissions: {
        Row: {
          evidence_sha256: string
          pack_count: number
          policy_version: string
          published_at: string
          resource_sha256s: string[]
          url: string
          verified_at: string
        }
        Insert: {
          evidence_sha256: string
          pack_count: number
          policy_version: string
          published_at: string
          resource_sha256s: string[]
          url: string
          verified_at: string
        }
        Update: {
          evidence_sha256?: string
          pack_count?: number
          policy_version?: string
          published_at?: string
          resource_sha256s?: string[]
          url?: string
          verified_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "numbered_family_admissions_url_fkey"
            columns: ["url"]
            isOneToOne: true
            referencedRelation: "numbered_family_candidates"
            referencedColumns: ["url"]
          },
        ]
      }
      numbered_family_candidates: {
        Row: {
          checked_at: string | null
          discovered_at: string
          state: string
          url: string
        }
        Insert: {
          checked_at?: string | null
          discovered_at?: string
          state?: string
          url: string
        }
        Update: {
          checked_at?: string | null
          discovered_at?: string
          state?: string
          url?: string
        }
        Relationships: []
      }
      numbered_family_control: {
        Row: {
          active_until: string
          discovered_at: string | null
          enabled: boolean
          last_request_at: string | null
          owner_generation: number | null
          owner_job_id: string | null
          policy_version: string
          singleton: boolean
        }
        Insert: {
          active_until?: string
          discovered_at?: string | null
          enabled?: boolean
          last_request_at?: string | null
          owner_generation?: number | null
          owner_job_id?: string | null
          policy_version: string
          singleton?: boolean
        }
        Update: {
          active_until?: string
          discovered_at?: string | null
          enabled?: boolean
          last_request_at?: string | null
          owner_generation?: number | null
          owner_job_id?: string | null
          policy_version?: string
          singleton?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "numbered_family_control_owner_job_id_fkey"
            columns: ["owner_job_id"]
            isOneToOne: false
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      numbered_family_identity_keys: {
        Row: {
          resource_sha256: string
          url_sha256: string
        }
        Insert: {
          resource_sha256: string
          url_sha256: string
        }
        Update: {
          resource_sha256?: string
          url_sha256?: string
        }
        Relationships: []
      }
      numbered_family_runs: {
        Row: {
          created_at: string
          generation: number
          job_id: string
          requests: number
          result: Json | null
          target_url: string
        }
        Insert: {
          created_at?: string
          generation: number
          job_id: string
          requests?: number
          result?: Json | null
          target_url: string
        }
        Update: {
          created_at?: string
          generation?: number
          job_id?: string
          requests?: number
          result?: Json | null
          target_url?: string
        }
        Relationships: [
          {
            foreignKeyName: "numbered_family_runs_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: true
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      opening_hits: {
        Row: {
          card_id: string | null
          card_name: string
          collector_number: string | null
          confidence: number
          created_at: string
          evidence_reference: string | null
          id: string
          is_demo: boolean
          opening_id: string
          quantity: number
          rarity: string
        }
        Insert: {
          card_id?: string | null
          card_name: string
          collector_number?: string | null
          confidence: number
          created_at?: string
          evidence_reference?: string | null
          id?: string
          is_demo?: boolean
          opening_id: string
          quantity?: number
          rarity: string
        }
        Update: {
          card_id?: string | null
          card_name?: string
          collector_number?: string | null
          confidence?: number
          created_at?: string
          evidence_reference?: string | null
          id?: string
          is_demo?: boolean
          opening_id?: string
          quantity?: number
          rarity?: string
        }
        Relationships: [
          {
            foreignKeyName: "opening_hits_opening_id_fkey"
            columns: ["opening_id"]
            isOneToOne: false
            referencedRelation: "openings"
            referencedColumns: ["id"]
          },
        ]
      }
      openings: {
        Row: {
          batch_code: string | null
          city: string | null
          complete_opening: boolean
          country_code: string | null
          created_at: string
          duplicate_of: string | null
          duplicate_suspected: boolean
          eligible_for_statistics: boolean
          evidence_tier: string
          expires_at: string
          extraction_run_id: string
          id: string
          is_demo: boolean
          language: string
          lot_code: string | null
          methodology_version: string
          observed_at: string
          opened_at: string | null
          overall_confidence: number
          pack_count: number
          product_id: string | null
          public_status: string
          purchase_date: string | null
          region_id: string | null
          retailer_id: string | null
          set_id: string
          source_item_id: string
          source_kind: string
          state_code: string | null
          store_id: string | null
          updated_at: string
          validation_status: string
        }
        Insert: {
          batch_code?: string | null
          city?: string | null
          complete_opening?: boolean
          country_code?: string | null
          created_at?: string
          duplicate_of?: string | null
          duplicate_suspected?: boolean
          eligible_for_statistics?: boolean
          evidence_tier: string
          expires_at?: string
          extraction_run_id: string
          id?: string
          is_demo?: boolean
          language?: string
          lot_code?: string | null
          methodology_version: string
          observed_at?: string
          opened_at?: string | null
          overall_confidence: number
          pack_count?: number
          product_id?: string | null
          public_status?: string
          purchase_date?: string | null
          region_id?: string | null
          retailer_id?: string | null
          set_id: string
          source_item_id: string
          source_kind: string
          state_code?: string | null
          store_id?: string | null
          updated_at?: string
          validation_status: string
        }
        Update: {
          batch_code?: string | null
          city?: string | null
          complete_opening?: boolean
          country_code?: string | null
          created_at?: string
          duplicate_of?: string | null
          duplicate_suspected?: boolean
          eligible_for_statistics?: boolean
          evidence_tier?: string
          expires_at?: string
          extraction_run_id?: string
          id?: string
          is_demo?: boolean
          language?: string
          lot_code?: string | null
          methodology_version?: string
          observed_at?: string
          opened_at?: string | null
          overall_confidence?: number
          pack_count?: number
          product_id?: string | null
          public_status?: string
          purchase_date?: string | null
          region_id?: string | null
          retailer_id?: string | null
          set_id?: string
          source_item_id?: string
          source_kind?: string
          state_code?: string | null
          store_id?: string | null
          updated_at?: string
          validation_status?: string
        }
        Relationships: [
          {
            foreignKeyName: "openings_duplicate_of_fkey"
            columns: ["duplicate_of"]
            isOneToOne: false
            referencedRelation: "openings"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "openings_extraction_run_id_fkey"
            columns: ["extraction_run_id"]
            isOneToOne: false
            referencedRelation: "extraction_runs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "openings_source_item_id_fkey"
            columns: ["source_item_id"]
            isOneToOne: false
            referencedRelation: "source_items"
            referencedColumns: ["id"]
          },
        ]
      }
      public_study_coverage_observations: {
        Row: {
          collector_version: string
          country_code: string
          country_name: string
          evidence_sha256: string
          first_verified_at: string
          is_demo: boolean
          last_verified_at: string
          pack_count: number
          parser_version: string
          product_scope: string
          set_external_id: string
          source_observed_at: string
          source_policy_id: string
          source_policy_version: string
          study_key: string
        }
        Insert: {
          collector_version: string
          country_code: string
          country_name: string
          evidence_sha256: string
          first_verified_at: string
          is_demo?: boolean
          last_verified_at: string
          pack_count: number
          parser_version: string
          product_scope: string
          set_external_id: string
          source_observed_at: string
          source_policy_id: string
          source_policy_version: string
          study_key: string
        }
        Update: {
          collector_version?: string
          country_code?: string
          country_name?: string
          evidence_sha256?: string
          first_verified_at?: string
          is_demo?: boolean
          last_verified_at?: string
          pack_count?: number
          parser_version?: string
          product_scope?: string
          set_external_id?: string
          source_observed_at?: string
          source_policy_id?: string
          source_policy_version?: string
          study_key?: string
        }
        Relationships: [
          {
            foreignKeyName: "public_study_coverage_observations_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: true
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      public_study_observations: {
        Row: {
          collector_version: string
          country_code: string
          country_name: string
          evidence_sha256: string
          extraction_run_id: string
          first_verified_at: string
          geography_basis: string
          geography_confidence: string
          is_demo: boolean
          last_verified_at: string
          metric_key: string
          metric_version: string
          opening_id: string
          pack_count: number
          parser_version: string
          product_scope: string
          qualifying_hit_pack_count: number
          set_external_id: string
          source_item_id: string
          source_observed_at: string
          source_policy_id: string
          source_policy_version: string
          study_key: string
        }
        Insert: {
          collector_version: string
          country_code: string
          country_name: string
          evidence_sha256: string
          extraction_run_id: string
          first_verified_at: string
          geography_basis: string
          geography_confidence: string
          is_demo?: boolean
          last_verified_at: string
          metric_key: string
          metric_version: string
          opening_id: string
          pack_count: number
          parser_version: string
          product_scope: string
          qualifying_hit_pack_count: number
          set_external_id: string
          source_item_id: string
          source_observed_at: string
          source_policy_id: string
          source_policy_version: string
          study_key: string
        }
        Update: {
          collector_version?: string
          country_code?: string
          country_name?: string
          evidence_sha256?: string
          extraction_run_id?: string
          first_verified_at?: string
          geography_basis?: string
          geography_confidence?: string
          is_demo?: boolean
          last_verified_at?: string
          metric_key?: string
          metric_version?: string
          opening_id?: string
          pack_count?: number
          parser_version?: string
          product_scope?: string
          qualifying_hit_pack_count?: number
          set_external_id?: string
          source_item_id?: string
          source_observed_at?: string
          source_policy_id?: string
          source_policy_version?: string
          study_key?: string
        }
        Relationships: [
          {
            foreignKeyName: "public_study_observations_extraction_run_id_fkey"
            columns: ["extraction_run_id"]
            isOneToOne: true
            referencedRelation: "extraction_runs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "public_study_observations_opening_id_fkey"
            columns: ["opening_id"]
            isOneToOne: true
            referencedRelation: "openings"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "public_study_observations_source_item_id_fkey"
            columns: ["source_item_id"]
            isOneToOne: true
            referencedRelation: "source_items"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "public_study_observations_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      research_intake_control: {
        Row: {
          enabled: boolean
          singleton: boolean
        }
        Insert: {
          enabled?: boolean
          singleton?: boolean
        }
        Update: {
          enabled?: boolean
          singleton?: boolean
        }
        Relationships: []
      }
      research_intake_references: {
        Row: {
          conflicting: boolean
          first_seen_at: string
          last_seen_at: string
          report_group_sha256: string
          snapshot_sha256: string
          url: string
        }
        Insert: {
          conflicting?: boolean
          first_seen_at?: string
          last_seen_at?: string
          report_group_sha256: string
          snapshot_sha256: string
          url: string
        }
        Update: {
          conflicting?: boolean
          first_seen_at?: string
          last_seen_at?: string
          report_group_sha256?: string
          snapshot_sha256?: string
          url?: string
        }
        Relationships: []
      }
      schedule_slots: {
        Row: {
          created_at: string
          job_id: string | null
          schedule_name: string
          slot_at: string
        }
        Insert: {
          created_at?: string
          job_id?: string | null
          schedule_name: string
          slot_at: string
        }
        Update: {
          created_at?: string
          job_id?: string | null
          schedule_name?: string
          slot_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "schedule_slots_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      source_family_admissions: {
        Row: {
          opening_ordinal: number
          pack_count: number
          policy_version: string
          post_id: number
          product: string
          published_at: string
          resource_sha256: string
          url: string
          verified_at: string
          video_sha256: string | null
        }
        Insert: {
          opening_ordinal: number
          pack_count: number
          policy_version: string
          post_id: number
          product: string
          published_at: string
          resource_sha256: string
          url: string
          verified_at: string
          video_sha256?: string | null
        }
        Update: {
          opening_ordinal?: number
          pack_count?: number
          policy_version?: string
          post_id?: number
          product?: string
          published_at?: string
          resource_sha256?: string
          url?: string
          verified_at?: string
          video_sha256?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "source_family_admissions_url_fkey"
            columns: ["url"]
            isOneToOne: true
            referencedRelation: "source_family_candidates"
            referencedColumns: ["url"]
          },
        ]
      }
      source_family_candidates: {
        Row: {
          checked_at: string | null
          discovered_at: string
          reason: string
          state: string
          url: string
        }
        Insert: {
          checked_at?: string | null
          discovered_at?: string
          reason?: string
          state?: string
          url: string
        }
        Update: {
          checked_at?: string | null
          discovered_at?: string
          reason?: string
          state?: string
          url?: string
        }
        Relationships: []
      }
      source_family_clock: {
        Row: {
          discovered_at: string | null
          singleton: boolean
        }
        Insert: {
          discovered_at?: string | null
          singleton?: boolean
        }
        Update: {
          discovered_at?: string | null
          singleton?: boolean
        }
        Relationships: []
      }
      source_family_control: {
        Row: {
          enabled: boolean
          policy_version: string
          singleton: boolean
        }
        Insert: {
          enabled?: boolean
          policy_version: string
          singleton?: boolean
        }
        Update: {
          enabled?: boolean
          policy_version?: string
          singleton?: boolean
        }
        Relationships: []
      }
      source_family_identity_keys: {
        Row: {
          identity_sha256: string
          url_sha256: string
        }
        Insert: {
          identity_sha256: string
          url_sha256: string
        }
        Update: {
          identity_sha256?: string
          url_sha256?: string
        }
        Relationships: []
      }
      source_family_runs: {
        Row: {
          created_at: string
          generation: number
          job_id: string
          last_request_at: string | null
          requests: number
          result: Json | null
          target_url: string
        }
        Insert: {
          created_at?: string
          generation: number
          job_id: string
          last_request_at?: string | null
          requests?: number
          result?: Json | null
          target_url: string
        }
        Update: {
          created_at?: string
          generation?: number
          job_id?: string
          last_request_at?: string | null
          requests?: number
          result?: Json | null
          target_url?: string
        }
        Relationships: [
          {
            foreignKeyName: "source_family_runs_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: true
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      source_family_tombstones: {
        Row: {
          reason: string
          url_sha256: string
        }
        Insert: {
          reason: string
          url_sha256: string
        }
        Update: {
          reason?: string
          url_sha256?: string
        }
        Relationships: []
      }
      source_items: {
        Row: {
          access_mode: string
          attempt_count: number
          audio_fingerprint: string | null
          author_hash: string | null
          collector_type: string
          collector_version: string
          content_hash: string
          created_at: string
          discovered_at: string
          domain: string
          duplicate_cluster_id: string | null
          duplicate_suspected: boolean
          expires_at: string
          external_id: string | null
          id: string
          is_demo: boolean
          language: string
          last_error_at: string | null
          last_error_code: string | null
          last_error_message: string | null
          media_hash: string | null
          metadata: Json
          normalized_url: string
          platform: string | null
          published_at: string | null
          source_kind: string
          source_policy_id: string
          source_policy_version: string
          source_url: string
          status: string
          text_excerpt: string | null
          title: string | null
          updated_at: string
          usage_classification: string
          video_fingerprint: string | null
        }
        Insert: {
          access_mode: string
          attempt_count?: number
          audio_fingerprint?: string | null
          author_hash?: string | null
          collector_type: string
          collector_version: string
          content_hash: string
          created_at?: string
          discovered_at?: string
          domain: string
          duplicate_cluster_id?: string | null
          duplicate_suspected?: boolean
          expires_at?: string
          external_id?: string | null
          id?: string
          is_demo?: boolean
          language?: string
          last_error_at?: string | null
          last_error_code?: string | null
          last_error_message?: string | null
          media_hash?: string | null
          metadata?: Json
          normalized_url: string
          platform?: string | null
          published_at?: string | null
          source_kind?: string
          source_policy_id: string
          source_policy_version: string
          source_url: string
          status?: string
          text_excerpt?: string | null
          title?: string | null
          updated_at?: string
          usage_classification?: string
          video_fingerprint?: string | null
        }
        Update: {
          access_mode?: string
          attempt_count?: number
          audio_fingerprint?: string | null
          author_hash?: string | null
          collector_type?: string
          collector_version?: string
          content_hash?: string
          created_at?: string
          discovered_at?: string
          domain?: string
          duplicate_cluster_id?: string | null
          duplicate_suspected?: boolean
          expires_at?: string
          external_id?: string | null
          id?: string
          is_demo?: boolean
          language?: string
          last_error_at?: string | null
          last_error_code?: string | null
          last_error_message?: string | null
          media_hash?: string | null
          metadata?: Json
          normalized_url?: string
          platform?: string | null
          published_at?: string | null
          source_kind?: string
          source_policy_id?: string
          source_policy_version?: string
          source_url?: string
          status?: string
          text_excerpt?: string | null
          title?: string | null
          updated_at?: string
          usage_classification?: string
          video_fingerprint?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "source_items_duplicate_cluster_mode_fkey"
            columns: ["duplicate_cluster_id", "is_demo"]
            isOneToOne: false
            referencedRelation: "source_items"
            referencedColumns: ["id", "is_demo"]
          },
          {
            foreignKeyName: "source_items_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
      source_policies: {
        Row: {
          access_mode: string
          base_url: string | null
          browser_profile: string | null
          collector_type: string
          config: Json
          created_at: string
          display_name: string
          domain: string
          enabled: boolean
          expected_interval_seconds: number
          id: string
          include_subdomains: boolean
          is_demo: boolean
          last_attempt_at: string | null
          last_failure_at: string | null
          last_success_at: string | null
          max_concurrency: number
          max_items_per_run: number
          max_pages_per_run: number
          min_delay_seconds: number
          retention_days: number
          robots_policy: string
          routes: string[]
          source_key: string
          source_kind: string
          statistics_eligible_default: boolean
          updated_at: string
          version: string
        }
        Insert: {
          access_mode: string
          base_url?: string | null
          browser_profile?: string | null
          collector_type: string
          config?: Json
          created_at?: string
          display_name: string
          domain: string
          enabled?: boolean
          expected_interval_seconds?: number
          id?: string
          include_subdomains?: boolean
          is_demo?: boolean
          last_attempt_at?: string | null
          last_failure_at?: string | null
          last_success_at?: string | null
          max_concurrency?: number
          max_items_per_run?: number
          max_pages_per_run?: number
          min_delay_seconds?: number
          retention_days?: number
          robots_policy?: string
          routes?: string[]
          source_key: string
          source_kind?: string
          statistics_eligible_default?: boolean
          updated_at?: string
          version?: string
        }
        Update: {
          access_mode?: string
          base_url?: string | null
          browser_profile?: string | null
          collector_type?: string
          config?: Json
          created_at?: string
          display_name?: string
          domain?: string
          enabled?: boolean
          expected_interval_seconds?: number
          id?: string
          include_subdomains?: boolean
          is_demo?: boolean
          last_attempt_at?: string | null
          last_failure_at?: string | null
          last_success_at?: string | null
          max_concurrency?: number
          max_items_per_run?: number
          max_pages_per_run?: number
          min_delay_seconds?: number
          retention_days?: number
          robots_policy?: string
          routes?: string[]
          source_key?: string
          source_kind?: string
          statistics_eligible_default?: boolean
          updated_at?: string
          version?: string
        }
        Relationships: []
      }
      source_request_gates: {
        Row: {
          acquired_at: string | null
          active_until: string | null
          owner_job_id: string | null
          owner_lease_generation: number | null
          source_key: string
        }
        Insert: {
          acquired_at?: string | null
          active_until?: string | null
          owner_job_id?: string | null
          owner_lease_generation?: number | null
          source_key: string
        }
        Update: {
          acquired_at?: string | null
          active_until?: string | null
          owner_job_id?: string | null
          owner_lease_generation?: number | null
          source_key?: string
        }
        Relationships: []
      }
      worker_heartbeats: {
        Row: {
          current_job_id: string | null
          is_demo: boolean
          last_seen_at: string
          metadata: Json
          version: string
          worker_id: string
          worker_type: string
        }
        Insert: {
          current_job_id?: string | null
          is_demo?: boolean
          last_seen_at?: string
          metadata?: Json
          version: string
          worker_id: string
          worker_type: string
        }
        Update: {
          current_job_id?: string | null
          is_demo?: boolean
          last_seen_at?: string
          metadata?: Json
          version?: string
          worker_id?: string
          worker_type?: string
        }
        Relationships: [
          {
            foreignKeyName: "worker_heartbeats_current_job_id_fkey"
            columns: ["current_job_id"]
            isOneToOne: false
            referencedRelation: "jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      youtube_discoveries: {
        Row: {
          created_at: string
          expires_at: string
          first_seen_at: string
          is_demo: boolean
          last_seen_at: string
          published_at: string | null
          source_policy_id: string
          source_url: string
          title: string | null
          updated_at: string
          video_id: string
        }
        Insert: {
          created_at?: string
          expires_at: string
          first_seen_at: string
          is_demo?: boolean
          last_seen_at: string
          published_at?: string | null
          source_policy_id: string
          source_url: string
          title?: string | null
          updated_at?: string
          video_id: string
        }
        Update: {
          created_at?: string
          expires_at?: string
          first_seen_at?: string
          is_demo?: boolean
          last_seen_at?: string
          published_at?: string | null
          source_policy_id?: string
          source_url?: string
          title?: string | null
          updated_at?: string
          video_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "youtube_discoveries_source_policy_id_fkey"
            columns: ["source_policy_id"]
            isOneToOne: false
            referencedRelation: "source_policies"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      admin_control_and_audit_v1: {
        Args: {
          p_action: string
          p_actor_email: string
          p_actor_id: string
          p_source_url?: string
          p_target_id?: string
        }
        Returns: Json
      }
      authorize_numbered_family_request_v1: {
        Args: {
          p_generation: number
          p_job: string
          p_url: string
          p_worker: string
        }
        Returns: boolean
      }
      authorize_source_family_request_v1: {
        Args: {
          p_generation: number
          p_job: string
          p_url: string
          p_worker: string
        }
        Returns: boolean
      }
      begin_bluesky_jetstream_job: {
        Args: { job_id: string; lease_generation: number; worker_id: string }
        Returns: {
          acquired: boolean
          retry_at: string
          start_cursor: number
        }[]
      }
      begin_bluesky_jetstream_job_v1: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_worker_id: string
        }
        Returns: {
          acquired: boolean
          retry_at: string
          start_cursor: number
        }[]
      }
      begin_mastodon_public_hashtag_job: {
        Args: {
          instance_key: string
          job_id: string
          lease_generation: number
          tag_key: string
          worker_id: string
        }
        Returns: {
          acquired: boolean
          cooldown_until: string
          retry_at: string
          start_status_id: string
        }[]
      }
      begin_nostr_relay_job: {
        Args: {
          job_id: string
          lease_generation: number
          relay_key: string
          worker_id: string
        }
        Returns: {
          acquired: boolean
          checkpoint: string
          recent_candidate_ids: string[]
          retry_at: string
          since: string
          until: string
        }[]
      }
      begin_numbered_family_v1: {
        Args: { p_generation: number; p_job: string; p_worker: string }
        Returns: {
          target_url: string
        }[]
      }
      begin_public_study_job: {
        Args: { job_id: string; lease_generation: number; worker_id: string }
        Returns: {
          acquired: boolean
          retry_at: string
        }[]
      }
      begin_public_study_job_v2: {
        Args: {
          job_id: string
          lease_generation: number
          study_key: string
          worker_id: string
        }
        Returns: {
          acquired: boolean
          retry_at: string
        }[]
      }
      begin_source_family_v1: {
        Args: { p_generation: number; p_job: string; p_worker: string }
        Returns: {
          product_name: string
          target_url: string
        }[]
      }
      begin_tcgdex_sets_job: {
        Args: { job_id: string; lease_generation: number; worker_id: string }
        Returns: {
          acquired: boolean
          content_sha256: string
          etag: string
          item_count: number
          retry_at: string
          revision: number
        }[]
      }
      begin_youtube_discovery_job: {
        Args: { job_id: string; lease_generation: number; worker_id: string }
        Returns: {
          acquired: boolean
          retry_at: string
        }[]
      }
      bluesky_cursor_v1: { Args: { value: string }; Returns: number }
      bluesky_timestamp_v1: {
        Args: { upper_bound: string; value: string }
        Returns: string
      }
      bluesky_worker_runtime_ready_v1: { Args: never; Returns: boolean }
      claim_bluesky_jetstream_jobs_v1: {
        Args: { p_lease_seconds: number; p_worker_id: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      claim_jobs: {
        Args: {
          batch_size?: number
          job_types?: string[]
          lease_seconds?: number
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      claim_jobs_v2: {
        Args: {
          batch_size?: number
          job_types?: string[]
          lease_seconds?: number
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      claim_nostr_relay_jobs_v1: {
        Args: { p_lease_seconds: number; p_worker_id: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      complete_job_v2: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      defer_numbered_family_v1: {
        Args: {
          p_generation: number
          p_job: string
          p_until: string
          p_worker: string
        }
        Returns: boolean
      }
      enqueue_due_bluesky_jetstream_jobs_v1: {
        Args: { p_worker_id: string }
        Returns: number
      }
      enqueue_due_nostr_relay_jobs_v1: {
        Args: { p_worker_id: string }
        Returns: number
      }
      enqueue_job_v1: {
        Args: {
          p_available_at?: string
          p_dedupe_key?: string
          p_job_type: string
          p_max_attempts?: number
          p_payload?: Json
          p_priority?: number
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_numbered_family_v1: {
        Args: { p_slot: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_pokesup_sv8_backfill_v1: {
        Args: never
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_pokesup_variable_layout_backfill_v1: {
        Args: never
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_public_study_coverage_job_v1: {
        Args: {
          p_available_at?: string
          p_dedupe_key?: string
          p_max_attempts?: number
          p_priority?: number
          p_study_key: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_scheduled_job_v1: {
        Args: {
          job_type: string
          max_attempts?: number
          payload?: Json
          priority?: number
          schedule_name: string
          scheduled_for: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_scheduled_public_study_coverage_job_v1: {
        Args: {
          p_max_attempts?: number
          p_priority?: number
          p_schedule_name: string
          p_scheduled_for: string
          p_study_key: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_source_family_v1: {
        Args: { p_slot: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      fail_bluesky_jetstream_job_v1: {
        Args: {
          p_error_code: string
          p_error_message: string
          p_job_id: string
          p_lease_generation: number
          p_retryable: boolean
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      fail_job_v2: {
        Args: {
          error_code: string
          error_message: string
          job_id: string
          lease_generation: number
          retryable: boolean
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      fail_nostr_relay_job_v1: {
        Args: {
          p_error_code: string
          p_error_message: string
          p_job_id: string
          p_lease_generation: number
          p_retryable: boolean
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_bluesky_jetstream_job: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_bluesky_jetstream_job_v1: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_result: Json
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_cleanup_job: {
        Args: { job_id: string; lease_generation: number; worker_id: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_mastodon_public_hashtag_job: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_nostr_relay_job: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_numbered_family_v1: {
        Args: { p_generation: number; p_job: string; p_worker: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_public_study_coverage_job_v1: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          study_key: string
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_public_study_job: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_source_family_v1: {
        Args: { p_generation: number; p_job: string; p_worker: string }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_tcgdex_sets_job: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      finalize_youtube_discovery_job: {
        Args: {
          job_id: string
          lease_generation: number
          result: Json
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      get_admin_dashboard_snapshot_v1: { Args: never; Returns: Json }
      get_bluesky_worker_policy_snapshot_v1: {
        Args: never
        Returns: {
          access_mode: string
          base_url: string
          browser_profile: string
          collector_type: string
          config: Json
          display_name: string
          domain: string
          enabled: boolean
          expected_interval_seconds: number
          include_subdomains: boolean
          is_demo: boolean
          max_concurrency: number
          max_items_per_run: number
          max_pages_per_run: number
          min_delay_seconds: number
          retention_days: number
          robots_policy: string
          routes: string[]
          source_key: string
          source_kind: string
          statistics_eligible_default: boolean
          version: string
        }[]
      }
      get_nostr_worker_policy_snapshot_v1: {
        Args: never
        Returns: {
          access_mode: string
          base_url: string
          browser_profile: string
          collector_type: string
          config: Json
          display_name: string
          domain: string
          enabled: boolean
          expected_interval_seconds: number
          include_subdomains: boolean
          is_demo: boolean
          max_concurrency: number
          max_items_per_run: number
          max_pages_per_run: number
          min_delay_seconds: number
          retention_days: number
          robots_policy: string
          routes: string[]
          source_key: string
          source_kind: string
          statistics_eligible_default: boolean
          version: string
        }[]
      }
      get_runtime_release_evidence_v1:
        | {
            Args: {
              p_grace_seconds?: number
              p_heartbeat_stale_seconds?: number
              p_release_started_at?: string
            }
            Returns: Json
          }
        | {
            Args: {
              p_grace_seconds: number
              p_heartbeat_stale_seconds: number
              p_release_started_at: string
              p_service_set: string
            }
            Returns: Json
          }
      heartbeat_bluesky_jetstream_job_v1: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_lease_seconds: number
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      heartbeat_job_v2: {
        Args: {
          job_id: string
          lease_generation: number
          lease_seconds: number
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      heartbeat_nostr_relay_job_v1: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_lease_seconds: number
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      import_research_intake_v1: { Args: { p_manifest: Json }; Returns: Json }
      list_authorized_opening_reviews_v1: {
        Args: { requested_limit: number; requested_state: string }
        Returns: {
          country_code: string
          created_at: string
          denominator_complete: boolean
          discovery_platform: string
          expires_at: string
          geography_basis: string
          geography_confidence: string
          language: string
          observed_at: string
          pack_count: number
          product_scope: string
          qualifying_hit_pack_count: number
          revision: number
          state: string
          statistics_eligible_requested: boolean
          submission_id: string
          tcgdex_set_id: string
          updated_at: string
        }[]
      }
      mastodon_status_id_v1: { Args: { value: string }; Returns: string }
      mastodon_tag_keys_v1: { Args: { value: string[] }; Returns: boolean }
      mastodon_timestamp_v1: {
        Args: { lower_bound: string; upper_bound: string; value: string }
        Returns: string
      }
      nostr_timestamp_v1: {
        Args: { lower_bound: string; upper_bound: string; value: string }
        Returns: string
      }
      nostr_worker_runtime_ready_v1: { Args: never; Returns: boolean }
      numbered_family_access_v1: { Args: never; Returns: boolean }
      numbered_family_ready_v1: { Args: never; Returns: boolean }
      pause_bluesky_jetstream_job_v1: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_retry_at: string
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      pause_job_for_budget_v2: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_retry_at: string
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      pause_nostr_relay_job_v1: {
        Args: {
          p_job_id: string
          p_lease_generation: number
          p_retry_at: string
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      prune_bluesky_jetstream_v1: {
        Args: { cutoff: string; max_rows?: number }
        Returns: {
          candidates_deleted: number
          observations_deleted: number
        }[]
      }
      prune_expired_ephemera: {
        Args: { cutoff?: string; max_rows?: number }
        Returns: Json
      }
      prune_expired_ephemera_v2: {
        Args: { cutoff?: string; max_rows?: number }
        Returns: Json
      }
      prune_mastodon_public_hashtag_v1: {
        Args: { cutoff: string; max_rows?: number }
        Returns: {
          candidates_deleted: number
          observations_deleted: number
        }[]
      }
      prune_nostr_relay_v1: {
        Args: { cutoff: string; max_rows?: number }
        Returns: {
          candidates_deleted: number
          observations_deleted: number
        }[]
      }
      record_mastodon_rate_limit: {
        Args: {
          job_id: string
          lease_generation: number
          retry_at: string
          worker_id: string
        }
        Returns: {
          recorded: boolean
        }[]
      }
      recover_bluesky_cursor_too_old_job_v1: {
        Args: {
          expected_start_cursor: number
          job_id: string
          lease_generation: number
          worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      recover_bluesky_cursor_too_old_job_v2: {
        Args: {
          p_expected_start_cursor: number
          p_job_id: string
          p_lease_generation: number
          p_worker_id: string
        }
        Returns: {
          attempts: number
          available_at: string
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          id: string
          is_demo: boolean
          job_type: string
          last_error_code: string | null
          last_error_message: string | null
          lease_generation: number
          lock_expires_at: string | null
          locked_at: string | null
          locked_by: string | null
          max_attempts: number
          payload: Json
          priority: number
          retention_until: string
          status: string
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      research_reference_url_valid_v1: {
        Args: { p_url: string }
        Returns: boolean
      }
      retract_authorized_opening_v1: {
        Args: {
          requested_observation_id: string
          requested_reason_code: string
          reviewer_reference_sha256: string
        }
        Returns: {
          accepted_observation_id: string
          reason_code: string
          retracted_at: string
        }[]
      }
      retract_numbered_family_v1: {
        Args: { p_url: string }
        Returns: undefined
      }
      retract_source_family_v1: { Args: { p_url: string }; Returns: undefined }
      review_authorized_opening_v1: {
        Args: {
          expected_revision: number
          reason_code: string
          requested_submission_id: string
          reviewer_reference_sha256: string
          target_state: string
        }
        Returns: {
          accepted_observation_id: string
          revision: number
          state: string
          submission_id: string
        }[]
      }
      reviewed_public_study_contracts: {
        Args: never
        Returns: {
          canonical_url: string
          config: Json
          display_name: string
          domain: string
          evidence_excerpt: string
          ordinal: number
          policy_key: string
          policy_version: string
          public_id: string
          public_name: string
          public_note: string
          study_key: string
          title_fragments: string[]
        }[]
      }
      reviewed_public_study_gates_ready_v1: { Args: never; Returns: boolean }
      source_family_access_v1: { Args: never; Returns: boolean }
      source_family_expected_labels_v1: {
        Args: { p_product: string }
        Returns: Json
      }
      source_family_pack_count_v1: {
        Args: { p_product: string }
        Returns: number
      }
      source_family_policy_v1: {
        Args: never
        Returns: {
          approved: boolean
          family: string
          review_expires_at: string
          version: string
        }[]
      }
      source_family_product_name_v1: {
        Args: { p_product: string }
        Returns: string
      }
      source_family_public_rows_v1: {
        Args: never
        Returns: {
          attribution_basis: string
          canonical_url: string
          configured_set_name: string
          country_code: string
          country_name: string
          domain: string
          last_verified_at: string
          ordinal: number
          pack_count: number
          product_scope: string
          public_id: string
          public_name: string
          public_note: string
          publisher_identity: string
          set_external_id: string
          set_language: string
          source_observed_at: string
          study_key: string
        }[]
      }
      source_family_ready_v1: { Args: never; Returns: boolean }
      source_family_resource_paths_v1: {
        Args: { p_product: string; p_slug: string; p_width: number }
        Returns: string[]
      }
      stage_numbered_family_v1: {
        Args: {
          p_generation: number
          p_job: string
          p_result: Json
          p_worker: string
        }
        Returns: undefined
      }
      stage_source_family_v1: {
        Args: {
          p_generation: number
          p_job: string
          p_result: Json
          p_worker: string
        }
        Returns: undefined
      }
      submit_authorized_opening_direct_v1: {
        Args: { payload: Json }
        Returns: {
          revision: number
          state: string
          submission_id: string
        }[]
      }
      submit_authorized_opening_v1: {
        Args: { payload: Json }
        Returns: {
          revision: number
          state: string
          submission_id: string
        }[]
      }
      upsert_bluesky_worker_heartbeat_v1: {
        Args: { p_metadata: Json; p_version: string; p_worker_id: string }
        Returns: {
          last_seen_at: string
        }[]
      }
      upsert_nostr_worker_heartbeat_v1: {
        Args: { p_metadata: Json; p_version: string; p_worker_id: string }
        Returns: {
          last_seen_at: string
        }[]
      }
      upsert_worker_heartbeat_v1: {
        Args: {
          p_metadata: Json
          p_version: string
          p_worker_id: string
          p_worker_type: string
        }
        Returns: {
          last_seen_at: string
        }[]
      }
      verify_bluesky_release_v1: { Args: never; Returns: Json }
      verify_nostr_release_v1: { Args: never; Returns: Json }
      verify_nostr_release_v2: { Args: never; Returns: Json }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  public: {
    Tables: {
      batch_summaries: {
        Row: {
          baseline_rate: number | null
          batch_code: string
          complete_openings: number
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          delta_from_baseline: number | null
          first_observed_at: string
          id: string
          independent_source_count: number
          is_demo: boolean
          last_observed_at: string
          methodology_version: string
          observed_packs: number
          observed_rate: number | null
          posterior_mean: number | null
          product_type: string
          region_id: string
          region_name: string
          set_id: string
          set_name: string
          set_slug: string
          signal_status: string
          updated_at: string
        }
        Insert: {
          baseline_rate?: number | null
          batch_code: string
          complete_openings?: number
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          first_observed_at: string
          id: string
          independent_source_count?: number
          is_demo?: boolean
          last_observed_at: string
          methodology_version: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          product_type: string
          region_id: string
          region_name: string
          set_id: string
          set_name: string
          set_slug: string
          signal_status: string
          updated_at: string
        }
        Update: {
          baseline_rate?: number | null
          batch_code?: string
          complete_openings?: number
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          first_observed_at?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          last_observed_at?: string
          methodology_version?: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          product_type?: string
          region_id?: string
          region_name?: string
          set_id?: string
          set_name?: string
          set_slug?: string
          signal_status?: string
          updated_at?: string
        }
        Relationships: []
      }
      country_period_map_cells: {
        Row: {
          baseline_rate: number | null
          complete_openings: number
          country_code: string
          country_name: string
          credible_interval_high: number | null
          credible_interval_low: number | null
          delta_from_baseline: number | null
          independent_source_count: number
          is_demo: boolean
          language: string
          methodology_version: string
          metric_key: string
          metric_version: string
          observed_packs: number
          observed_rate: number | null
          period_end: string
          period_start: string
          posterior_mean: number | null
          product_scope: string
          set_scope: string
          signal_status: string
          updated_at: string
        }
        Insert: {
          baseline_rate?: number | null
          complete_openings: number
          country_code: string
          country_name: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          delta_from_baseline?: number | null
          independent_source_count: number
          is_demo?: boolean
          language: string
          methodology_version: string
          metric_key: string
          metric_version: string
          observed_packs: number
          observed_rate?: number | null
          period_end: string
          period_start: string
          posterior_mean?: number | null
          product_scope?: string
          set_scope?: string
          signal_status: string
          updated_at: string
        }
        Update: {
          baseline_rate?: number | null
          complete_openings?: number
          country_code?: string
          country_name?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          delta_from_baseline?: number | null
          independent_source_count?: number
          is_demo?: boolean
          language?: string
          methodology_version?: string
          metric_key?: string
          metric_version?: string
          observed_packs?: number
          observed_rate?: number | null
          period_end?: string
          period_start?: string
          posterior_mean?: number | null
          product_scope?: string
          set_scope?: string
          signal_status?: string
          updated_at?: string
        }
        Relationships: []
      }
      dashboard_overview: {
        Row: {
          accepted_count: number
          activity_only_count: number
          australia_coverage: string
          baseline_hit_rate: number | null
          batch_sightings: number
          complete_openings: number
          coverage_days: number
          generated_at: string
          is_demo: boolean
          methodology_version: string
          mode: string
          observed_packs: number
          rejected_count: number
          schema_version: string
          snapshot_key: string
          tracked_regions: number
          tracked_retailers: number
          tracked_sets: number
          verified_sources: number
        }
        Insert: {
          accepted_count?: number
          activity_only_count?: number
          australia_coverage: string
          baseline_hit_rate?: number | null
          batch_sightings?: number
          complete_openings?: number
          coverage_days?: number
          generated_at: string
          is_demo?: boolean
          methodology_version: string
          mode: string
          observed_packs?: number
          rejected_count?: number
          schema_version?: string
          snapshot_key: string
          tracked_regions?: number
          tracked_retailers?: number
          tracked_sets?: number
          verified_sources?: number
        }
        Update: {
          accepted_count?: number
          activity_only_count?: number
          australia_coverage?: string
          baseline_hit_rate?: number | null
          batch_sightings?: number
          complete_openings?: number
          coverage_days?: number
          generated_at?: string
          is_demo?: boolean
          methodology_version?: string
          mode?: string
          observed_packs?: number
          rejected_count?: number
          schema_version?: string
          snapshot_key?: string
          tracked_regions?: number
          tracked_retailers?: number
          tracked_sets?: number
          verified_sources?: number
        }
        Relationships: []
      }
      data_freshness: {
        Row: {
          age_seconds: number | null
          as_of: string
          component_id: string
          component_name: string
          is_demo: boolean
          last_successful_collection_at: string | null
          next_expected_at: string | null
          status: string
        }
        Insert: {
          age_seconds?: number | null
          as_of: string
          component_id: string
          component_name: string
          is_demo?: boolean
          last_successful_collection_at?: string | null
          next_expected_at?: string | null
          status: string
        }
        Update: {
          age_seconds?: number | null
          as_of?: string
          component_id?: string
          component_name?: string
          is_demo?: boolean
          last_successful_collection_at?: string | null
          next_expected_at?: string | null
          status?: string
        }
        Relationships: []
      }
      public_signals: {
        Row: {
          as_of: string
          baseline: number | null
          baseline_scope: string
          complete_openings: number
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          entity_key: string
          entity_label: string
          entity_type: string
          evidence_tier: string
          id: string
          independent_source_count: number
          is_demo: boolean
          methodology_version: string
          metric: string
          observed: number | null
          posterior_mean: number | null
          probability_above_baseline: number | null
          probability_above_practical_uplift: number | null
          sample_size: number
          set_id: string | null
          status: string
          window_end: string
          window_start: string
        }
        Insert: {
          as_of: string
          baseline?: number | null
          baseline_scope: string
          complete_openings: number
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          entity_key: string
          entity_label: string
          entity_type: string
          evidence_tier: string
          id: string
          independent_source_count: number
          is_demo?: boolean
          methodology_version: string
          metric: string
          observed?: number | null
          posterior_mean?: number | null
          probability_above_baseline?: number | null
          probability_above_practical_uplift?: number | null
          sample_size: number
          set_id?: string | null
          status: string
          window_end: string
          window_start: string
        }
        Update: {
          as_of?: string
          baseline?: number | null
          baseline_scope?: string
          complete_openings?: number
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          entity_key?: string
          entity_label?: string
          entity_type?: string
          evidence_tier?: string
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          methodology_version?: string
          metric?: string
          observed?: number | null
          posterior_mean?: number | null
          probability_above_baseline?: number | null
          probability_above_practical_uplift?: number | null
          sample_size?: number
          set_id?: string | null
          status?: string
          window_end?: string
          window_start?: string
        }
        Relationships: []
      }
      recent_activity: {
        Row: {
          activity_kind: string
          country_code: string
          created_at: string
          entities: Json
          evidence_tier: string
          id: string
          is_demo: boolean
          observed_at: string
          occurred_at: string
          pack_count: number | null
          platform: string | null
          product_type: string | null
          region_name: string | null
          retailer_name: string
          set_name: string
          source_kind: string
          source_link: string | null
          source_published_at: string | null
          source_title: string | null
          statistics_eligible: boolean
          status: string
          subject_id: string
          subject_kind: string
          subject_label: string
        }
        Insert: {
          activity_kind: string
          country_code: string
          created_at?: string
          entities?: Json
          evidence_tier: string
          id: string
          is_demo?: boolean
          observed_at: string
          occurred_at: string
          pack_count?: number | null
          platform?: string | null
          product_type?: string | null
          region_name?: string | null
          retailer_name: string
          set_name: string
          source_kind: string
          source_link?: string | null
          source_published_at?: string | null
          source_title?: string | null
          statistics_eligible?: boolean
          status: string
          subject_id: string
          subject_kind: string
          subject_label: string
        }
        Update: {
          activity_kind?: string
          country_code?: string
          created_at?: string
          entities?: Json
          evidence_tier?: string
          id?: string
          is_demo?: boolean
          observed_at?: string
          occurred_at?: string
          pack_count?: number | null
          platform?: string | null
          product_type?: string | null
          region_name?: string | null
          retailer_name?: string
          set_name?: string
          source_kind?: string
          source_link?: string | null
          source_published_at?: string | null
          source_title?: string | null
          statistics_eligible?: boolean
          status?: string
          subject_id?: string
          subject_kind?: string
          subject_label?: string
        }
        Relationships: []
      }
      region_summaries: {
        Row: {
          baseline_rate: number | null
          complete_openings: number
          country_code: string
          coverage: string
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          delta_from_baseline: number | null
          independent_source_count: number
          is_demo: boolean
          methodology_version: string
          name: string
          observed_packs: number
          observed_rate: number | null
          posterior_mean: number | null
          region_id: string
          signal_status: string
          slug: string
          updated_at: string
        }
        Insert: {
          baseline_rate?: number | null
          complete_openings?: number
          country_code: string
          coverage: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          independent_source_count?: number
          is_demo?: boolean
          methodology_version: string
          name: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          region_id: string
          signal_status: string
          slug: string
          updated_at: string
        }
        Update: {
          baseline_rate?: number | null
          complete_openings?: number
          country_code?: string
          coverage?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          independent_source_count?: number
          is_demo?: boolean
          methodology_version?: string
          name?: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          region_id?: string
          signal_status?: string
          slug?: string
          updated_at?: string
        }
        Relationships: []
      }
      retailer_summaries: {
        Row: {
          baseline_rate: number | null
          channel: string
          complete_openings: number
          country_code: string
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          delta_from_baseline: number | null
          id: string
          independent_source_count: number
          is_demo: boolean
          methodology_version: string
          name: string
          observed_packs: number
          observed_rate: number | null
          posterior_mean: number | null
          region_id: string
          region_name: string
          retailer_id: string
          signal_status: string
          slug: string
          updated_at: string
        }
        Insert: {
          baseline_rate?: number | null
          channel: string
          complete_openings?: number
          country_code: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          id: string
          independent_source_count?: number
          is_demo?: boolean
          methodology_version: string
          name: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          region_id: string
          region_name: string
          retailer_id: string
          signal_status: string
          slug: string
          updated_at: string
        }
        Update: {
          baseline_rate?: number | null
          channel?: string
          complete_openings?: number
          country_code?: string
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          id?: string
          independent_source_count?: number
          is_demo?: boolean
          methodology_version?: string
          name?: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          region_id?: string
          region_name?: string
          retailer_id?: string
          signal_status?: string
          slug?: string
          updated_at?: string
        }
        Relationships: []
      }
      set_summaries: {
        Row: {
          baseline_rate: number | null
          complete_openings: number
          credible_interval_high: number | null
          credible_interval_low: number | null
          credible_level: number
          delta_from_baseline: number | null
          independent_source_count: number
          is_demo: boolean
          methodology_version: string
          name: string
          observed_packs: number
          observed_rate: number | null
          posterior_mean: number | null
          release_date: string
          series_name: string
          set_id: string
          signal_status: string
          slug: string
          updated_at: string
        }
        Insert: {
          baseline_rate?: number | null
          complete_openings?: number
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          independent_source_count?: number
          is_demo?: boolean
          methodology_version: string
          name: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          release_date: string
          series_name: string
          set_id: string
          signal_status: string
          slug: string
          updated_at: string
        }
        Update: {
          baseline_rate?: number | null
          complete_openings?: number
          credible_interval_high?: number | null
          credible_interval_low?: number | null
          credible_level?: number
          delta_from_baseline?: number | null
          independent_source_count?: number
          is_demo?: boolean
          methodology_version?: string
          name?: string
          observed_packs?: number
          observed_rate?: number | null
          posterior_mean?: number | null
          release_date?: string
          series_name?: string
          set_id?: string
          signal_status?: string
          slug?: string
          updated_at?: string
        }
        Relationships: []
      }
      system_status: {
        Row: {
          auth_required: boolean
          checked_at: string
          component_id: string
          component_name: string
          is_demo: boolean
          public_message: string | null
          status: string
        }
        Insert: {
          auth_required?: boolean
          checked_at: string
          component_id: string
          component_name: string
          is_demo?: boolean
          public_message?: string | null
          status: string
        }
        Update: {
          auth_required?: boolean
          checked_at?: string
          component_id?: string
          component_name?: string
          is_demo?: boolean
          public_message?: string | null
          status?: string
        }
        Relationships: []
      }
      tcgdex_catalog_status: {
        Row: {
          is_current: boolean
          is_demo: boolean
          language: string
          last_changed_at: string
          last_checked_at: string
          revision: number
          scope: string
          set_count: number
          source: string
        }
        Insert: {
          is_current: boolean
          is_demo: boolean
          language: string
          last_changed_at: string
          last_checked_at: string
          revision: number
          scope: string
          set_count: number
          source: string
        }
        Update: {
          is_current?: boolean
          is_demo?: boolean
          language?: string
          last_changed_at?: string
          last_checked_at?: string
          revision?: number
          scope?: string
          set_count?: number
          source?: string
        }
        Relationships: []
      }
      tcgdex_set_index: {
        Row: {
          is_current: boolean
          is_demo: boolean
          language: string
          name: string
          refreshed_at: string
          release_date: string | null
          series_name: string | null
          set_id: string
          slug: string
        }
        Insert: {
          is_current: boolean
          is_demo: boolean
          language: string
          name: string
          refreshed_at: string
          release_date?: string | null
          series_name?: string | null
          set_id: string
          slug: string
        }
        Update: {
          is_current?: boolean
          is_demo?: boolean
          language?: string
          name?: string
          refreshed_at?: string
          release_date?: string | null
          series_name?: string | null
          set_id?: string
          slug?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      admin_control_and_audit_v1: {
        Args: {
          p_action: string
          p_actor_email: string
          p_actor_id: string
          p_source_url?: string
          p_target_id?: string
        }
        Returns: Json
      }
      get_admin_dashboard_snapshot_v1: { Args: never; Returns: Json }
      get_public_dashboard_snapshot_v1: { Args: never; Returns: Json }
      get_public_dashboard_snapshot_v2: { Args: never; Returns: Json }
      get_public_dashboard_snapshot_v3: { Args: never; Returns: Json }
      get_public_social_discovery_v1: { Args: never; Returns: Json }
      get_public_social_discovery_v2: { Args: never; Returns: Json }
      get_public_social_discovery_v3: { Args: never; Returns: Json }
      get_public_social_discovery_v4: { Args: never; Returns: Json }
      get_public_study_coverage_v1: { Args: never; Returns: Json }
      get_public_study_coverage_v2: { Args: never; Returns: Json }
      get_public_study_coverage_v3: { Args: never; Returns: Json }
      get_public_study_coverage_v4: { Args: never; Returns: Json }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  analytics: {
    Enums: {},
  },
  catalog: {
    Enums: {},
  },
  ingest: {
    Enums: {},
  },
  public: {
    Enums: {},
  },
} as const
