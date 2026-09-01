// Hand-generated-style bridge for Supabase clients.
// Regenerate with `supabase gen types typescript --local` once the live CLI is available.
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type ProductType = 'booster_box' | 'etb' | 'booster_bundle' | 'blister' | 'collection' | 'tin' | 'other';
export type PublicSignalStatus = 'Insufficient sample' | 'No significant signal' | 'Watch' | 'Possible anomaly';

export type Database = {
  public: {
    Tables: {
      country_period_map_cells: {
        Row: {
          country_code: string;
          country_name: string;
          period_start: string;
          period_end: string;
          language: string;
          set_scope: string;
          product_scope: string;
          metric_key: string;
          metric_version: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          observed_rate: number | null;
          posterior_mean: number | null;
          baseline_rate: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          delta_from_baseline: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo: boolean;
        };
        Insert: {
          country_code: string;
          country_name: string;
          period_start: string;
          period_end: string;
          language: string;
          set_scope?: string;
          product_scope?: string;
          metric_key: string;
          metric_version: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          delta_from_baseline?: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo?: boolean;
        };
        Update: {
          country_code?: string;
          country_name?: string;
          period_start?: string;
          period_end?: string;
          language?: string;
          set_scope?: string;
          product_scope?: string;
          metric_key?: string;
          metric_version?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          delta_from_baseline?: number | null;
          signal_status?: string;
          methodology_version?: string;
          updated_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'country_period_map_cells_country_code_fkey';
            columns: ['country_code'];
            isOneToOne: false;
            referencedRelation: 'iso_alpha2_codes';
            referencedColumns: ['code'];
          },
        ];
      };
      tcgdex_catalog_status: {
        Row: {
          source: string;
          scope: string;
          language: string;
          revision: number;
          set_count: number;
          last_checked_at: string;
          last_changed_at: string;
          is_current: boolean;
          is_demo: boolean;
        };
        Insert: {
          source: string;
          scope: string;
          language: string;
          revision: number;
          set_count: number;
          last_checked_at: string;
          last_changed_at: string;
          is_current: boolean;
          is_demo: boolean;
        };
        Update: {
          source?: string;
          scope?: string;
          language?: string;
          revision?: number;
          set_count?: number;
          last_checked_at?: string;
          last_changed_at?: string;
          is_current?: boolean;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      tcgdex_set_index: {
        Row: {
          set_id: string;
          slug: string;
          name: string;
          series_name: string | null;
          release_date: string | null;
          language: string;
          is_current: boolean;
          refreshed_at: string;
          is_demo: boolean;
        };
        Insert: {
          set_id: string;
          slug: string;
          name: string;
          series_name?: string | null;
          release_date?: string | null;
          language: string;
          is_current: boolean;
          refreshed_at: string;
          is_demo: boolean;
        };
        Update: {
          set_id?: string;
          slug?: string;
          name?: string;
          series_name?: string | null;
          release_date?: string | null;
          language?: string;
          is_current?: boolean;
          refreshed_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      batch_summaries: {
        Row: {
          id: string;
          batch_code: string;
          set_id: string;
          set_slug: string;
          set_name: string;
          product_type: string;
          region_id: string;
          region_name: string;
          first_observed_at: string;
          last_observed_at: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          observed_rate: number | null;
          posterior_mean: number | null;
          baseline_rate: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          delta_from_baseline: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo: boolean;
        };
        Insert: {
          id: string;
          batch_code: string;
          set_id: string;
          set_slug: string;
          set_name: string;
          product_type: string;
          region_id: string;
          region_name: string;
          first_observed_at: string;
          last_observed_at: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          batch_code?: string;
          set_id?: string;
          set_slug?: string;
          set_name?: string;
          product_type?: string;
          region_id?: string;
          region_name?: string;
          first_observed_at?: string;
          last_observed_at?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status?: string;
          methodology_version?: string;
          updated_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      dashboard_overview: {
        Row: {
          snapshot_key: string;
          schema_version: string;
          mode: string;
          generated_at: string;
          observed_packs: number;
          complete_openings: number;
          verified_sources: number;
          coverage_days: number;
          tracked_sets: number;
          tracked_regions: number;
          tracked_retailers: number;
          batch_sightings: number;
          australia_coverage: string;
          baseline_hit_rate: number | null;
          accepted_count: number;
          activity_only_count: number;
          rejected_count: number;
          methodology_version: string;
          is_demo: boolean;
        };
        Insert: {
          snapshot_key: string;
          schema_version?: string;
          mode: string;
          generated_at: string;
          observed_packs?: number;
          complete_openings?: number;
          verified_sources?: number;
          coverage_days?: number;
          tracked_sets?: number;
          tracked_regions?: number;
          tracked_retailers?: number;
          batch_sightings?: number;
          australia_coverage: string;
          baseline_hit_rate?: number | null;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          methodology_version: string;
          is_demo?: boolean;
        };
        Update: {
          snapshot_key?: string;
          schema_version?: string;
          mode?: string;
          generated_at?: string;
          observed_packs?: number;
          complete_openings?: number;
          verified_sources?: number;
          coverage_days?: number;
          tracked_sets?: number;
          tracked_regions?: number;
          tracked_retailers?: number;
          batch_sightings?: number;
          australia_coverage?: string;
          baseline_hit_rate?: number | null;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          methodology_version?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      data_freshness: {
        Row: {
          component_id: string;
          component_name: string;
          status: string;
          as_of: string;
          last_successful_collection_at: string | null;
          age_seconds: number | null;
          next_expected_at: string | null;
          is_demo: boolean;
        };
        Insert: {
          component_id: string;
          component_name: string;
          status: string;
          as_of: string;
          last_successful_collection_at?: string | null;
          age_seconds?: number | null;
          next_expected_at?: string | null;
          is_demo?: boolean;
        };
        Update: {
          component_id?: string;
          component_name?: string;
          status?: string;
          as_of?: string;
          last_successful_collection_at?: string | null;
          age_seconds?: number | null;
          next_expected_at?: string | null;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      public_signals: {
        Row: {
          id: string;
          entity_type: string;
          entity_key: string;
          entity_label: string;
          set_id: string | null;
          metric: string;
          status: string;
          sample_size: number;
          complete_openings: number;
          independent_source_count: number;
          baseline: number | null;
          observed: number | null;
          posterior_mean: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          probability_above_baseline: number | null;
          probability_above_practical_uplift: number | null;
          baseline_scope: string;
          evidence_tier: string;
          window_start: string;
          window_end: string;
          methodology_version: string;
          as_of: string;
          is_demo: boolean;
        };
        Insert: {
          id: string;
          entity_type: string;
          entity_key: string;
          entity_label: string;
          set_id?: string | null;
          metric: string;
          status: string;
          sample_size: number;
          complete_openings: number;
          independent_source_count: number;
          baseline?: number | null;
          observed?: number | null;
          posterior_mean?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          probability_above_baseline?: number | null;
          probability_above_practical_uplift?: number | null;
          baseline_scope: string;
          evidence_tier: string;
          window_start: string;
          window_end: string;
          methodology_version: string;
          as_of: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          entity_type?: string;
          entity_key?: string;
          entity_label?: string;
          set_id?: string | null;
          metric?: string;
          status?: string;
          sample_size?: number;
          complete_openings?: number;
          independent_source_count?: number;
          baseline?: number | null;
          observed?: number | null;
          posterior_mean?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          probability_above_baseline?: number | null;
          probability_above_practical_uplift?: number | null;
          baseline_scope?: string;
          evidence_tier?: string;
          window_start?: string;
          window_end?: string;
          methodology_version?: string;
          as_of?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      recent_activity: {
        Row: {
          id: string;
          activity_kind: string;
          subject_kind: string;
          subject_id: string;
          subject_label: string;
          set_name: string;
          retailer_name: string;
          occurred_at: string;
          observed_at: string;
          pack_count: number | null;
          product_type: string | null;
          evidence_tier: string;
          status: string;
          statistics_eligible: boolean;
          country_code: string;
          region_name: string | null;
          platform: string | null;
          source_kind: string;
          source_title: string | null;
          source_published_at: string | null;
          source_link: string | null;
          entities: Json;
          is_demo: boolean;
          created_at: string;
        };
        Insert: {
          id: string;
          activity_kind: string;
          subject_kind: string;
          subject_id: string;
          subject_label: string;
          set_name: string;
          retailer_name: string;
          occurred_at: string;
          observed_at: string;
          pack_count?: number | null;
          product_type?: string | null;
          evidence_tier: string;
          status: string;
          statistics_eligible?: boolean;
          country_code: string;
          region_name?: string | null;
          platform?: string | null;
          source_kind: string;
          source_title?: string | null;
          source_published_at?: string | null;
          source_link?: string | null;
          entities?: Json;
          is_demo?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          activity_kind?: string;
          subject_kind?: string;
          subject_id?: string;
          subject_label?: string;
          set_name?: string;
          retailer_name?: string;
          occurred_at?: string;
          observed_at?: string;
          pack_count?: number | null;
          product_type?: string | null;
          evidence_tier?: string;
          status?: string;
          statistics_eligible?: boolean;
          country_code?: string;
          region_name?: string | null;
          platform?: string | null;
          source_kind?: string;
          source_title?: string | null;
          source_published_at?: string | null;
          source_link?: string | null;
          entities?: Json;
          is_demo?: boolean;
          created_at?: string;
        };
        Relationships: [
        ];
      };
      region_summaries: {
        Row: {
          region_id: string;
          slug: string;
          name: string;
          country_code: string;
          coverage: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          observed_rate: number | null;
          posterior_mean: number | null;
          baseline_rate: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          delta_from_baseline: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo: boolean;
        };
        Insert: {
          region_id: string;
          slug: string;
          name: string;
          country_code: string;
          coverage: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo?: boolean;
        };
        Update: {
          region_id?: string;
          slug?: string;
          name?: string;
          country_code?: string;
          coverage?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status?: string;
          methodology_version?: string;
          updated_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      retailer_summaries: {
        Row: {
          id: string;
          retailer_id: string;
          region_id: string;
          slug: string;
          name: string;
          region_name: string;
          country_code: string;
          channel: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          observed_rate: number | null;
          posterior_mean: number | null;
          baseline_rate: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          delta_from_baseline: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo: boolean;
        };
        Insert: {
          id: string;
          retailer_id: string;
          region_id: string;
          slug: string;
          name: string;
          region_name: string;
          country_code: string;
          channel: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          retailer_id?: string;
          region_id?: string;
          slug?: string;
          name?: string;
          region_name?: string;
          country_code?: string;
          channel?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status?: string;
          methodology_version?: string;
          updated_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      set_summaries: {
        Row: {
          set_id: string;
          slug: string;
          name: string;
          series_name: string;
          release_date: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          observed_rate: number | null;
          posterior_mean: number | null;
          baseline_rate: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          delta_from_baseline: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo: boolean;
        };
        Insert: {
          set_id: string;
          slug: string;
          name: string;
          series_name: string;
          release_date: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status: string;
          methodology_version: string;
          updated_at: string;
          is_demo?: boolean;
        };
        Update: {
          set_id?: string;
          slug?: string;
          name?: string;
          series_name?: string;
          release_date?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          observed_rate?: number | null;
          posterior_mean?: number | null;
          baseline_rate?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          delta_from_baseline?: number | null;
          signal_status?: string;
          methodology_version?: string;
          updated_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      system_status: {
        Row: {
          component_id: string;
          component_name: string;
          status: string;
          checked_at: string;
          public_message: string | null;
          auth_required: boolean;
          is_demo: boolean;
        };
        Insert: {
          component_id: string;
          component_name: string;
          status: string;
          checked_at: string;
          public_message?: string | null;
          auth_required?: boolean;
          is_demo?: boolean;
        };
        Update: {
          component_id?: string;
          component_name?: string;
          status?: string;
          checked_at?: string;
          public_message?: string | null;
          auth_required?: boolean;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
      get_admin_dashboard_snapshot_v1: { Args: Record<PropertyKey, never>; Returns: Json };
      admin_control_and_audit_v1: {
        Args: {
          p_action: string;
          p_actor_id: string;
          p_actor_email: string;
          p_source_url?: string | null;
          p_target_id?: string | null;
        };
        Returns: Json;
      };
      get_public_dashboard_snapshot_v1: { Args: Record<PropertyKey, never>; Returns: Json };
      get_public_dashboard_snapshot_v2: { Args: Record<PropertyKey, never>; Returns: Json };
      get_public_dashboard_snapshot_v3: { Args: Record<PropertyKey, never>; Returns: Json };
      get_public_social_discovery_v1: { Args: Record<PropertyKey, never>; Returns: Json };
      get_public_social_discovery_v2: { Args: Record<PropertyKey, never>; Returns: Json };
      get_public_study_coverage_v1: { Args: Record<PropertyKey, never>; Returns: Json };
    };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
  catalog: {
    Tables: {
      iso_alpha2_codes: {
        Row: {
          code: string;
        };
        Insert: {
          code: string;
        };
        Update: {
          code?: string;
        };
        Relationships: [
        ];
      };
      cards: {
        Row: {
          id: string;
          external_source: string;
          external_id: string;
          set_id: string;
          name: string;
          collector_number: string | null;
          rarity: string | null;
          language: string;
          metadata: Json;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          external_source: string;
          external_id: string;
          set_id: string;
          name: string;
          collector_number?: string | null;
          rarity?: string | null;
          language?: string;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          external_source?: string;
          external_id?: string;
          set_id?: string;
          name?: string;
          collector_number?: string | null;
          rarity?: string | null;
          language?: string;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'cards_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
      products: {
        Row: {
          id: string;
          set_id: string | null;
          name: string;
          slug: string;
          product_type: string;
          language: string;
          sku: string | null;
          upc: string | null;
          ean: string | null;
          declared_pack_count: number | null;
          metadata: Json;
          is_active: boolean;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          set_id?: string | null;
          name: string;
          slug: string;
          product_type: string;
          language?: string;
          sku?: string | null;
          upc?: string | null;
          ean?: string | null;
          declared_pack_count?: number | null;
          metadata?: Json;
          is_active?: boolean;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          set_id?: string | null;
          name?: string;
          slug?: string;
          product_type?: string;
          language?: string;
          sku?: string | null;
          upc?: string | null;
          ean?: string | null;
          declared_pack_count?: number | null;
          metadata?: Json;
          is_active?: boolean;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'products_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
      regions: {
        Row: {
          id: string;
          country_code: string;
          state_code: string | null;
          city: string | null;
          name: string;
          slug: string;
          region_type: string;
          parent_id: string | null;
          latitude: number | null;
          longitude: number | null;
          metadata: Json;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          country_code: string;
          state_code?: string | null;
          city?: string | null;
          name: string;
          slug: string;
          region_type: string;
          parent_id?: string | null;
          latitude?: number | null;
          longitude?: number | null;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          country_code?: string;
          state_code?: string | null;
          city?: string | null;
          name?: string;
          slug?: string;
          region_type?: string;
          parent_id?: string | null;
          latitude?: number | null;
          longitude?: number | null;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'regions_parent_id_fkey';
            columns: ['parent_id'];
            isOneToOne: false;
            referencedRelation: 'regions';
            referencedColumns: ['id'];
          },
        ];
      };
      retailers: {
        Row: {
          id: string;
          name: string;
          slug: string;
          country_code: string | null;
          website_domain: string | null;
          metadata: Json;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          slug: string;
          country_code?: string | null;
          website_domain?: string | null;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          name?: string;
          slug?: string;
          country_code?: string | null;
          website_domain?: string | null;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
        ];
      };
      sets: {
        Row: {
          id: string;
          external_source: string;
          external_id: string;
          name: string;
          slug: string;
          set_code: string | null;
          language: string;
          release_date: string | null;
          series_name: string | null;
          rarity_taxonomy: Json;
          metadata: Json;
          is_active: boolean;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          external_source: string;
          external_id: string;
          name: string;
          slug: string;
          set_code?: string | null;
          language?: string;
          release_date?: string | null;
          series_name?: string | null;
          rarity_taxonomy?: Json;
          metadata?: Json;
          is_active?: boolean;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          external_source?: string;
          external_id?: string;
          name?: string;
          slug?: string;
          set_code?: string | null;
          language?: string;
          release_date?: string | null;
          series_name?: string | null;
          rarity_taxonomy?: Json;
          metadata?: Json;
          is_active?: boolean;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
        ];
      };
      stores: {
        Row: {
          id: string;
          retailer_id: string;
          region_id: string | null;
          name: string;
          slug: string;
          public_address: string | null;
          latitude: number | null;
          longitude: number | null;
          metadata: Json;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          retailer_id: string;
          region_id?: string | null;
          name: string;
          slug: string;
          public_address?: string | null;
          latitude?: number | null;
          longitude?: number | null;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          retailer_id?: string;
          region_id?: string | null;
          name?: string;
          slug?: string;
          public_address?: string | null;
          latitude?: number | null;
          longitude?: number | null;
          metadata?: Json;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'stores_region_id_fkey';
            columns: ['region_id'];
            isOneToOne: false;
            referencedRelation: 'regions';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'stores_retailer_id_fkey';
            columns: ['retailer_id'];
            isOneToOne: false;
            referencedRelation: 'retailers';
            referencedColumns: ['id'];
          },
        ];
      };
      sync_state: {
        Row: {
          source: string;
          scope: string;
          language: string;
          is_demo: boolean;
          revision: number;
          etag: string | null;
          content_sha256: string;
          item_count: number;
          last_checked_at: string;
          last_changed_at: string;
          last_job_id: string | null;
        };
        Insert: {
          source: string;
          scope: string;
          language: string;
          is_demo?: boolean;
          revision?: number;
          etag?: string | null;
          content_sha256: string;
          item_count: number;
          last_checked_at: string;
          last_changed_at: string;
          last_job_id?: string | null;
        };
        Update: {
          source?: string;
          scope?: string;
          language?: string;
          is_demo?: boolean;
          revision?: number;
          etag?: string | null;
          content_sha256?: string;
          item_count?: number;
          last_checked_at?: string;
          last_changed_at?: string;
          last_job_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'sync_state_last_job_id_fkey';
            columns: ['last_job_id'];
            isOneToOne: false;
            referencedRelation: 'jobs';
            referencedColumns: ['id'];
          },
        ];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
    };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
  ingest: {
    Tables: {
      admin_audit_log: {
        Row: {
          id: string;
          actor_id: string | null;
          actor_email_hash: string | null;
          action: string;
          object_type: string;
          object_id: string | null;
          detail: Json;
          ip_hash: string | null;
          occurred_at: string;
          retention_until: string;
          is_demo: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          actor_id?: string | null;
          actor_email_hash?: string | null;
          action: string;
          object_type: string;
          object_id?: string | null;
          detail?: Json;
          ip_hash?: string | null;
          occurred_at?: string;
          retention_until?: string;
          is_demo?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          actor_id?: string | null;
          actor_email_hash?: string | null;
          action?: string;
          object_type?: string;
          object_id?: string | null;
          detail?: Json;
          ip_hash?: string | null;
          occurred_at?: string;
          retention_until?: string;
          is_demo?: boolean;
          created_at?: string;
        };
        Relationships: [
        ];
      };
      ai_usage_daily: {
        Row: {
          date: string;
          provider: string;
          model: string;
          stage: string;
          request_count: number;
          input_tokens: number;
          output_tokens: number;
          estimated_cost_aud: number;
          is_demo: boolean;
        };
        Insert: {
          date: string;
          provider: string;
          model: string;
          stage: string;
          request_count?: number;
          input_tokens?: number;
          output_tokens?: number;
          estimated_cost_aud?: number;
          is_demo?: boolean;
        };
        Update: {
          date?: string;
          provider?: string;
          model?: string;
          stage?: string;
          request_count?: number;
          input_tokens?: number;
          output_tokens?: number;
          estimated_cost_aud?: number;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      batch_sightings: {
        Row: {
          id: string;
          source_item_id: string;
          opening_id: string | null;
          set_id: string | null;
          product_id: string | null;
          region_id: string | null;
          retailer_id: string | null;
          store_id: string | null;
          batch_code: string;
          normalized_batch_code: string;
          lot_code: string | null;
          normalized_lot_code: string | null;
          pack_quantity: number | null;
          activity_only: boolean;
          confidence: number;
          observed_at: string;
          expires_at: string;
          is_demo: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          source_item_id: string;
          opening_id?: string | null;
          set_id?: string | null;
          product_id?: string | null;
          region_id?: string | null;
          retailer_id?: string | null;
          store_id?: string | null;
          batch_code: string;
          normalized_batch_code: string;
          lot_code?: string | null;
          normalized_lot_code?: string | null;
          pack_quantity?: number | null;
          activity_only?: boolean;
          confidence: number;
          observed_at?: string;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          source_item_id?: string;
          opening_id?: string | null;
          set_id?: string | null;
          product_id?: string | null;
          region_id?: string | null;
          retailer_id?: string | null;
          store_id?: string | null;
          batch_code?: string;
          normalized_batch_code?: string;
          lot_code?: string | null;
          normalized_lot_code?: string | null;
          pack_quantity?: number | null;
          activity_only?: boolean;
          confidence?: number;
          observed_at?: string;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'batch_sightings_opening_id_fkey';
            columns: ['opening_id'];
            isOneToOne: false;
            referencedRelation: 'openings';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_sightings_product_id_fkey';
            columns: ['product_id'];
            isOneToOne: false;
            referencedRelation: 'products';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_sightings_region_id_fkey';
            columns: ['region_id'];
            isOneToOne: false;
            referencedRelation: 'regions';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_sightings_retailer_id_fkey';
            columns: ['retailer_id'];
            isOneToOne: false;
            referencedRelation: 'retailers';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_sightings_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_sightings_source_item_id_fkey';
            columns: ['source_item_id'];
            isOneToOne: false;
            referencedRelation: 'source_items';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_sightings_store_id_fkey';
            columns: ['store_id'];
            isOneToOne: false;
            referencedRelation: 'stores';
            referencedColumns: ['id'];
          },
        ];
      };
      browser_sessions: {
        Row: {
          profile_name: string;
          status: string;
          extension_connected: boolean;
          daemon_connected: boolean;
          authenticated_sources: Json;
          last_check_at: string;
          last_successful_command_at: string | null;
          last_error: string | null;
          is_demo: boolean;
        };
        Insert: {
          profile_name: string;
          status?: string;
          extension_connected?: boolean;
          daemon_connected?: boolean;
          authenticated_sources?: Json;
          last_check_at?: string;
          last_successful_command_at?: string | null;
          last_error?: string | null;
          is_demo?: boolean;
        };
        Update: {
          profile_name?: string;
          status?: string;
          extension_connected?: boolean;
          daemon_connected?: boolean;
          authenticated_sources?: Json;
          last_check_at?: string;
          last_successful_command_at?: string | null;
          last_error?: string | null;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      bluesky_jetstream_candidates: {
        Row: {
          at_uri: string;
          public_url: string;
          text_excerpt: string | null;
          record_sha256: string;
          published_at: string | null;
          source_policy_id: string;
          source_policy_version: string;
          collector_version: string;
          first_seen_at: string;
          last_seen_at: string;
          last_cursor: number;
          deleted_at: string | null;
          expires_at: string;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          at_uri: string;
          public_url: string;
          text_excerpt?: string | null;
          record_sha256: string;
          published_at?: string | null;
          source_policy_id: string;
          source_policy_version: string;
          collector_version: string;
          first_seen_at: string;
          last_seen_at: string;
          last_cursor: number;
          deleted_at?: string | null;
          expires_at: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          at_uri?: string;
          public_url?: string;
          text_excerpt?: string | null;
          record_sha256?: string;
          published_at?: string | null;
          source_policy_id?: string;
          source_policy_version?: string;
          collector_version?: string;
          first_seen_at?: string;
          last_seen_at?: string;
          last_cursor?: number;
          deleted_at?: string | null;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'bluesky_jetstream_candidates_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      bluesky_jetstream_observations: {
        Row: {
          id: number;
          source_policy_id: string;
          cursor: number;
          at_uri: string;
          operation: string;
          public_url: string | null;
          text_excerpt: string | null;
          record_sha256: string | null;
          published_at: string | null;
          observed_at: string;
          expires_at: string;
          is_demo: boolean;
        };
        Insert: {
          id?: number;
          source_policy_id: string;
          cursor: number;
          at_uri: string;
          operation: string;
          public_url?: string | null;
          text_excerpt?: string | null;
          record_sha256?: string | null;
          published_at?: string | null;
          observed_at: string;
          expires_at: string;
          is_demo?: boolean;
        };
        Update: {
          id?: number;
          source_policy_id?: string;
          cursor?: number;
          at_uri?: string;
          operation?: string;
          public_url?: string | null;
          text_excerpt?: string | null;
          record_sha256?: string | null;
          published_at?: string | null;
          observed_at?: string;
          expires_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'bluesky_jetstream_observations_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      bluesky_jetstream_checkpoints: {
        Row: {
          source_policy_id: string;
          endpoint: string;
          protocol: string;
          collection: string;
          last_cursor: number | null;
          last_collected_at: string | null;
          events_seen_total: number;
          bytes_seen_total: number;
          candidates_seen_total: number;
          deletions_seen_total: number;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          source_policy_id: string;
          endpoint: string;
          protocol: string;
          collection: string;
          last_cursor?: number | null;
          last_collected_at?: string | null;
          events_seen_total?: number;
          bytes_seen_total?: number;
          candidates_seen_total?: number;
          deletions_seen_total?: number;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          source_policy_id?: string;
          endpoint?: string;
          protocol?: string;
          collection?: string;
          last_cursor?: number | null;
          last_collected_at?: string | null;
          events_seen_total?: number;
          bytes_seen_total?: number;
          candidates_seen_total?: number;
          deletions_seen_total?: number;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'bluesky_jetstream_checkpoints_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: true;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      nostr_relay_candidates: {
        Row: {
          event_id: string;
          source_policy_id: string;
          relay_key: string;
          author_sha256: string;
          content_sha256: string;
          matched_tags: string[];
          published_at: string;
          first_seen_at: string;
          last_seen_at: string;
          deleted_at: string | null;
          expires_at: string;
          activity_only: boolean;
          statistics_eligible: boolean;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          event_id: string;
          source_policy_id: string;
          relay_key: string;
          author_sha256: string;
          content_sha256: string;
          matched_tags: string[];
          published_at: string;
          first_seen_at: string;
          last_seen_at: string;
          deleted_at?: string | null;
          expires_at: string;
          activity_only?: boolean;
          statistics_eligible?: boolean;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          event_id?: string;
          source_policy_id?: string;
          relay_key?: string;
          author_sha256?: string;
          content_sha256?: string;
          matched_tags?: string[];
          published_at?: string;
          first_seen_at?: string;
          last_seen_at?: string;
          deleted_at?: string | null;
          expires_at?: string;
          activity_only?: boolean;
          statistics_eligible?: boolean;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'nostr_relay_candidates_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      nostr_relay_observations: {
        Row: {
          id: number;
          relay_key: string;
          source_policy_id: string;
          event_id: string;
          operation: string;
          author_sha256: string;
          content_sha256: string | null;
          matched_tags: string[] | null;
          published_at: string;
          target_event_ids: string[];
          observed_at: string;
          expires_at: string;
          activity_only: boolean;
          statistics_eligible: boolean;
          is_demo: boolean;
        };
        Insert: {
          id?: number;
          relay_key: string;
          source_policy_id: string;
          event_id: string;
          operation: string;
          author_sha256: string;
          content_sha256?: string | null;
          matched_tags?: string[] | null;
          published_at: string;
          target_event_ids?: string[];
          observed_at: string;
          expires_at: string;
          activity_only?: boolean;
          statistics_eligible?: boolean;
          is_demo?: boolean;
        };
        Update: {
          id?: number;
          relay_key?: string;
          source_policy_id?: string;
          event_id?: string;
          operation?: string;
          author_sha256?: string;
          content_sha256?: string | null;
          matched_tags?: string[] | null;
          published_at?: string;
          target_event_ids?: string[];
          observed_at?: string;
          expires_at?: string;
          activity_only?: boolean;
          statistics_eligible?: boolean;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'nostr_relay_observations_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      nostr_relay_checkpoints: {
        Row: {
          source_policy_id: string;
          relay_key: string;
          endpoint: string;
          nip11_url: string;
          protocol: string;
          approved_tags: string[];
          last_checkpoint: string | null;
          events_seen_total: number;
          bytes_seen_total: number;
          candidates_seen_total: number;
          deletions_seen_total: number;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          source_policy_id: string;
          relay_key: string;
          endpoint: string;
          nip11_url: string;
          protocol: string;
          approved_tags: string[];
          last_checkpoint?: string | null;
          events_seen_total?: number;
          bytes_seen_total?: number;
          candidates_seen_total?: number;
          deletions_seen_total?: number;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          source_policy_id?: string;
          relay_key?: string;
          endpoint?: string;
          nip11_url?: string;
          protocol?: string;
          approved_tags?: string[];
          last_checkpoint?: string | null;
          events_seen_total?: number;
          bytes_seen_total?: number;
          candidates_seen_total?: number;
          deletions_seen_total?: number;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'nostr_relay_checkpoints_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: true;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      extraction_runs: {
        Row: {
          id: string;
          source_item_id: string;
          stage: string;
          provider: string;
          model: string;
          prompt_version: string;
          input_hash: string;
          output_json: Json | null;
          decision: string | null;
          confidence: number | null;
          input_tokens: number;
          output_tokens: number;
          estimated_cost_aud: number;
          latency_ms: number | null;
          error_code: string | null;
          error_message: string | null;
          started_at: string;
          completed_at: string | null;
          expires_at: string;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          source_item_id: string;
          stage: string;
          provider: string;
          model: string;
          prompt_version: string;
          input_hash: string;
          output_json?: Json | null;
          decision?: string | null;
          confidence?: number | null;
          input_tokens?: number;
          output_tokens?: number;
          estimated_cost_aud?: number;
          latency_ms?: number | null;
          error_code?: string | null;
          error_message?: string | null;
          started_at?: string;
          completed_at?: string | null;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          source_item_id?: string;
          stage?: string;
          provider?: string;
          model?: string;
          prompt_version?: string;
          input_hash?: string;
          output_json?: Json | null;
          decision?: string | null;
          confidence?: number | null;
          input_tokens?: number;
          output_tokens?: number;
          estimated_cost_aud?: number;
          latency_ms?: number | null;
          error_code?: string | null;
          error_message?: string | null;
          started_at?: string;
          completed_at?: string | null;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'extraction_runs_source_item_id_fkey';
            columns: ['source_item_id'];
            isOneToOne: false;
            referencedRelation: 'source_items';
            referencedColumns: ['id'];
          },
        ];
      };
      jobs: {
        Row: {
          id: string;
          job_type: string;
          payload: Json;
          status: string;
          priority: number;
          attempts: number;
          max_attempts: number;
          available_at: string;
          locked_at: string | null;
          lock_expires_at: string | null;
          locked_by: string | null;
          last_error_code: string | null;
          last_error_message: string | null;
          created_at: string;
          updated_at: string;
          completed_at: string | null;
          dedupe_key: string | null;
          retention_until: string;
          is_demo: boolean;
          lease_generation: number;
        };
        Insert: {
          id?: string;
          job_type: string;
          payload?: Json;
          status?: string;
          priority?: number;
          attempts?: number;
          max_attempts?: number;
          available_at?: string;
          locked_at?: string | null;
          lock_expires_at?: string | null;
          locked_by?: string | null;
          last_error_code?: string | null;
          last_error_message?: string | null;
          created_at?: string;
          updated_at?: string;
          completed_at?: string | null;
          dedupe_key?: string | null;
          retention_until?: string;
          is_demo?: boolean;
          lease_generation?: number;
        };
        Update: {
          id?: string;
          job_type?: string;
          payload?: Json;
          status?: string;
          priority?: number;
          attempts?: number;
          max_attempts?: number;
          available_at?: string;
          locked_at?: string | null;
          lock_expires_at?: string | null;
          locked_by?: string | null;
          last_error_code?: string | null;
          last_error_message?: string | null;
          created_at?: string;
          updated_at?: string;
          completed_at?: string | null;
          dedupe_key?: string | null;
          retention_until?: string;
          is_demo?: boolean;
          lease_generation?: number;
        };
        Relationships: [
        ];
      };
      opening_hits: {
        Row: {
          id: string;
          opening_id: string;
          card_id: string | null;
          card_name: string;
          collector_number: string | null;
          rarity: string;
          quantity: number;
          evidence_reference: string | null;
          confidence: number;
          is_demo: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          opening_id: string;
          card_id?: string | null;
          card_name: string;
          collector_number?: string | null;
          rarity: string;
          quantity?: number;
          evidence_reference?: string | null;
          confidence: number;
          is_demo?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          opening_id?: string;
          card_id?: string | null;
          card_name?: string;
          collector_number?: string | null;
          rarity?: string;
          quantity?: number;
          evidence_reference?: string | null;
          confidence?: number;
          is_demo?: boolean;
          created_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'opening_hits_card_id_fkey';
            columns: ['card_id'];
            isOneToOne: false;
            referencedRelation: 'cards';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'opening_hits_opening_id_fkey';
            columns: ['opening_id'];
            isOneToOne: false;
            referencedRelation: 'openings';
            referencedColumns: ['id'];
          },
        ];
      };
      openings: {
        Row: {
          id: string;
          source_item_id: string;
          extraction_run_id: string;
          set_id: string;
          product_id: string | null;
          language: string;
          pack_count: number;
          complete_opening: boolean;
          country_code: string | null;
          state_code: string | null;
          city: string | null;
          region_id: string | null;
          retailer_id: string | null;
          store_id: string | null;
          batch_code: string | null;
          lot_code: string | null;
          purchase_date: string | null;
          opened_at: string | null;
          observed_at: string;
          evidence_tier: string;
          overall_confidence: number;
          eligible_for_statistics: boolean;
          methodology_version: string;
          validation_status: string;
          public_status: string;
          source_kind: string;
          duplicate_of: string | null;
          duplicate_suspected: boolean;
          expires_at: string;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          source_item_id: string;
          extraction_run_id: string;
          set_id: string;
          product_id?: string | null;
          language?: string;
          pack_count?: number;
          complete_opening?: boolean;
          country_code?: string | null;
          state_code?: string | null;
          city?: string | null;
          region_id?: string | null;
          retailer_id?: string | null;
          store_id?: string | null;
          batch_code?: string | null;
          lot_code?: string | null;
          purchase_date?: string | null;
          opened_at?: string | null;
          observed_at?: string;
          evidence_tier: string;
          overall_confidence: number;
          eligible_for_statistics?: boolean;
          methodology_version: string;
          validation_status: string;
          public_status?: string;
          source_kind: string;
          duplicate_of?: string | null;
          duplicate_suspected?: boolean;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          source_item_id?: string;
          extraction_run_id?: string;
          set_id?: string;
          product_id?: string | null;
          language?: string;
          pack_count?: number;
          complete_opening?: boolean;
          country_code?: string | null;
          state_code?: string | null;
          city?: string | null;
          region_id?: string | null;
          retailer_id?: string | null;
          store_id?: string | null;
          batch_code?: string | null;
          lot_code?: string | null;
          purchase_date?: string | null;
          opened_at?: string | null;
          observed_at?: string;
          evidence_tier?: string;
          overall_confidence?: number;
          eligible_for_statistics?: boolean;
          methodology_version?: string;
          validation_status?: string;
          public_status?: string;
          source_kind?: string;
          duplicate_of?: string | null;
          duplicate_suspected?: boolean;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'openings_duplicate_of_fkey';
            columns: ['duplicate_of'];
            isOneToOne: false;
            referencedRelation: 'openings';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_extraction_run_id_fkey';
            columns: ['extraction_run_id'];
            isOneToOne: false;
            referencedRelation: 'extraction_runs';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_product_id_fkey';
            columns: ['product_id'];
            isOneToOne: false;
            referencedRelation: 'products';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_region_id_fkey';
            columns: ['region_id'];
            isOneToOne: false;
            referencedRelation: 'regions';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_retailer_id_fkey';
            columns: ['retailer_id'];
            isOneToOne: false;
            referencedRelation: 'retailers';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_source_item_id_fkey';
            columns: ['source_item_id'];
            isOneToOne: false;
            referencedRelation: 'source_items';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'openings_store_id_fkey';
            columns: ['store_id'];
            isOneToOne: false;
            referencedRelation: 'stores';
            referencedColumns: ['id'];
          },
        ];
      };
      public_study_coverage_observations: {
        Row: {
          study_key: string;
          source_policy_id: string;
          country_code: string;
          country_name: string;
          source_observed_at: string;
          pack_count: number;
          set_external_id: string;
          product_scope: string;
          collector_version: string;
          parser_version: string;
          source_policy_version: string;
          evidence_sha256: string;
          first_verified_at: string;
          last_verified_at: string;
          is_demo: boolean;
        };
        Insert: {
          study_key: string;
          source_policy_id: string;
          country_code: string;
          country_name: string;
          source_observed_at: string;
          pack_count: number;
          set_external_id: string;
          product_scope: string;
          collector_version: string;
          parser_version: string;
          source_policy_version: string;
          evidence_sha256: string;
          first_verified_at: string;
          last_verified_at: string;
          is_demo?: boolean;
        };
        Update: {
          study_key?: string;
          source_policy_id?: string;
          country_code?: string;
          country_name?: string;
          source_observed_at?: string;
          pack_count?: number;
          set_external_id?: string;
          product_scope?: string;
          collector_version?: string;
          parser_version?: string;
          source_policy_version?: string;
          evidence_sha256?: string;
          first_verified_at?: string;
          last_verified_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'public_study_coverage_observations_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: true;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      public_study_observations: {
        Row: {
          study_key: string;
          source_policy_id: string;
          source_item_id: string;
          extraction_run_id: string;
          opening_id: string;
          country_code: string;
          country_name: string;
          geography_basis: string;
          geography_confidence: string;
          source_observed_at: string;
          pack_count: number;
          qualifying_hit_pack_count: number;
          set_external_id: string;
          product_scope: string;
          metric_key: string;
          metric_version: string;
          collector_version: string;
          parser_version: string;
          source_policy_version: string;
          evidence_sha256: string;
          first_verified_at: string;
          last_verified_at: string;
          is_demo: boolean;
        };
        Insert: {
          study_key: string;
          source_policy_id: string;
          source_item_id: string;
          extraction_run_id: string;
          opening_id: string;
          country_code: string;
          country_name: string;
          geography_basis: string;
          geography_confidence: string;
          source_observed_at: string;
          pack_count: number;
          qualifying_hit_pack_count: number;
          set_external_id: string;
          product_scope: string;
          metric_key: string;
          metric_version: string;
          collector_version: string;
          parser_version: string;
          source_policy_version: string;
          evidence_sha256: string;
          first_verified_at: string;
          last_verified_at: string;
          is_demo?: boolean;
        };
        Update: {
          study_key?: string;
          source_policy_id?: string;
          source_item_id?: string;
          extraction_run_id?: string;
          opening_id?: string;
          country_code?: string;
          country_name?: string;
          geography_basis?: string;
          geography_confidence?: string;
          source_observed_at?: string;
          pack_count?: number;
          qualifying_hit_pack_count?: number;
          set_external_id?: string;
          product_scope?: string;
          metric_key?: string;
          metric_version?: string;
          collector_version?: string;
          parser_version?: string;
          source_policy_version?: string;
          evidence_sha256?: string;
          first_verified_at?: string;
          last_verified_at?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'public_study_observations_country_code_fkey';
            columns: ['country_code'];
            isOneToOne: false;
            referencedRelation: 'iso_alpha2_codes';
            referencedColumns: ['code'];
          },
          {
            foreignKeyName: 'public_study_observations_extraction_run_id_fkey';
            columns: ['extraction_run_id'];
            isOneToOne: true;
            referencedRelation: 'extraction_runs';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'public_study_observations_opening_id_fkey';
            columns: ['opening_id'];
            isOneToOne: true;
            referencedRelation: 'openings';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'public_study_observations_source_item_id_fkey';
            columns: ['source_item_id'];
            isOneToOne: true;
            referencedRelation: 'source_items';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'public_study_observations_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      schedule_slots: {
        Row: {
          schedule_name: string;
          slot_at: string;
          job_id: string | null;
          created_at: string;
        };
        Insert: {
          schedule_name: string;
          slot_at: string;
          job_id?: string | null;
          created_at?: string;
        };
        Update: {
          schedule_name?: string;
          slot_at?: string;
          job_id?: string | null;
          created_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'schedule_slots_job_id_fkey';
            columns: ['job_id'];
            isOneToOne: false;
            referencedRelation: 'jobs';
            referencedColumns: ['id'];
          },
        ];
      };
      youtube_discoveries: {
        Row: {
          video_id: string;
          source_policy_id: string;
          source_url: string;
          title: string | null;
          published_at: string | null;
          first_seen_at: string;
          last_seen_at: string;
          expires_at: string;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          video_id: string;
          source_policy_id: string;
          source_url: string;
          title?: string | null;
          published_at?: string | null;
          first_seen_at: string;
          last_seen_at: string;
          expires_at: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          video_id?: string;
          source_policy_id?: string;
          source_url?: string;
          title?: string | null;
          published_at?: string | null;
          first_seen_at?: string;
          last_seen_at?: string;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'youtube_discoveries_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      source_request_gates: {
        Row: {
          source_key: string;
          owner_job_id: string | null;
          owner_lease_generation: number | null;
          acquired_at: string | null;
          active_until: string | null;
        };
        Insert: {
          source_key: string;
          owner_job_id?: string | null;
          owner_lease_generation?: number | null;
          acquired_at?: string | null;
          active_until?: string | null;
        };
        Update: {
          source_key?: string;
          owner_job_id?: string | null;
          owner_lease_generation?: number | null;
          acquired_at?: string | null;
          active_until?: string | null;
        };
        Relationships: [];
      };
      source_items: {
        Row: {
          id: string;
          source_policy_id: string;
          platform: string | null;
          external_id: string | null;
          source_url: string;
          normalized_url: string;
          domain: string;
          title: string | null;
          text_excerpt: string | null;
          published_at: string | null;
          discovered_at: string;
          author_hash: string | null;
          content_hash: string;
          media_hash: string | null;
          video_fingerprint: string | null;
          audio_fingerprint: string | null;
          duplicate_cluster_id: string | null;
          duplicate_suspected: boolean;
          collector_type: string;
          collector_version: string;
          source_policy_version: string;
          access_mode: string;
          usage_classification: string;
          source_kind: string;
          language: string;
          status: string;
          attempt_count: number;
          last_error_code: string | null;
          last_error_message: string | null;
          last_error_at: string | null;
          metadata: Json;
          expires_at: string;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          source_policy_id: string;
          platform?: string | null;
          external_id?: string | null;
          source_url: string;
          normalized_url: string;
          domain: string;
          title?: string | null;
          text_excerpt?: string | null;
          published_at?: string | null;
          discovered_at?: string;
          author_hash?: string | null;
          content_hash: string;
          media_hash?: string | null;
          video_fingerprint?: string | null;
          audio_fingerprint?: string | null;
          duplicate_cluster_id?: string | null;
          duplicate_suspected?: boolean;
          collector_type: string;
          collector_version: string;
          source_policy_version: string;
          access_mode: string;
          usage_classification?: string;
          source_kind?: string;
          language?: string;
          status?: string;
          attempt_count?: number;
          last_error_code?: string | null;
          last_error_message?: string | null;
          last_error_at?: string | null;
          metadata?: Json;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          source_policy_id?: string;
          platform?: string | null;
          external_id?: string | null;
          source_url?: string;
          normalized_url?: string;
          domain?: string;
          title?: string | null;
          text_excerpt?: string | null;
          published_at?: string | null;
          discovered_at?: string;
          author_hash?: string | null;
          content_hash?: string;
          media_hash?: string | null;
          video_fingerprint?: string | null;
          audio_fingerprint?: string | null;
          duplicate_cluster_id?: string | null;
          duplicate_suspected?: boolean;
          collector_type?: string;
          collector_version?: string;
          source_policy_version?: string;
          access_mode?: string;
          usage_classification?: string;
          source_kind?: string;
          language?: string;
          status?: string;
          attempt_count?: number;
          last_error_code?: string | null;
          last_error_message?: string | null;
          last_error_at?: string | null;
          metadata?: Json;
          expires_at?: string;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'source_items_duplicate_cluster_mode_fkey';
            columns: ['duplicate_cluster_id', 'is_demo'];
            isOneToOne: false;
            referencedRelation: 'source_items';
            referencedColumns: ['id', 'is_demo'];
          },
          {
            foreignKeyName: 'source_items_source_policy_id_fkey';
            columns: ['source_policy_id'];
            isOneToOne: false;
            referencedRelation: 'source_policies';
            referencedColumns: ['id'];
          },
        ];
      };
      source_policies: {
        Row: {
          id: string;
          source_key: string;
          display_name: string;
          source_kind: string;
          domain: string;
          base_url: string | null;
          enabled: boolean;
          collector_type: string;
          access_mode: string;
          robots_policy: string;
          routes: string[];
          include_subdomains: boolean;
          min_delay_seconds: number;
          max_pages_per_run: number;
          max_items_per_run: number;
          max_concurrency: number;
          browser_profile: string | null;
          statistics_eligible_default: boolean;
          retention_days: number;
          config: Json;
          version: string;
          expected_interval_seconds: number;
          last_attempt_at: string | null;
          last_success_at: string | null;
          last_failure_at: string | null;
          is_demo: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          source_key: string;
          display_name: string;
          source_kind?: string;
          domain: string;
          base_url?: string | null;
          enabled?: boolean;
          collector_type: string;
          access_mode: string;
          robots_policy?: string;
          routes?: string[];
          include_subdomains?: boolean;
          min_delay_seconds?: number;
          max_pages_per_run?: number;
          max_items_per_run?: number;
          max_concurrency?: number;
          browser_profile?: string | null;
          statistics_eligible_default?: boolean;
          retention_days?: number;
          config?: Json;
          version?: string;
          expected_interval_seconds?: number;
          last_attempt_at?: string | null;
          last_success_at?: string | null;
          last_failure_at?: string | null;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          source_key?: string;
          display_name?: string;
          source_kind?: string;
          domain?: string;
          base_url?: string | null;
          enabled?: boolean;
          collector_type?: string;
          access_mode?: string;
          robots_policy?: string;
          routes?: string[];
          include_subdomains?: boolean;
          min_delay_seconds?: number;
          max_pages_per_run?: number;
          max_items_per_run?: number;
          max_concurrency?: number;
          browser_profile?: string | null;
          statistics_eligible_default?: boolean;
          retention_days?: number;
          config?: Json;
          version?: string;
          expected_interval_seconds?: number;
          last_attempt_at?: string | null;
          last_success_at?: string | null;
          last_failure_at?: string | null;
          is_demo?: boolean;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
        ];
      };
      worker_heartbeats: {
        Row: {
          worker_id: string;
          worker_type: string;
          version: string;
          last_seen_at: string;
          current_job_id: string | null;
          metadata: Json;
          is_demo: boolean;
        };
        Insert: {
          worker_id: string;
          worker_type: string;
          version: string;
          last_seen_at?: string;
          current_job_id?: string | null;
          metadata?: Json;
          is_demo?: boolean;
        };
        Update: {
          worker_id?: string;
          worker_type?: string;
          version?: string;
          last_seen_at?: string;
          current_job_id?: string | null;
          metadata?: Json;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'worker_heartbeats_current_job_id_fkey';
            columns: ['current_job_id'];
            isOneToOne: false;
            referencedRelation: 'jobs';
            referencedColumns: ['id'];
          },
        ];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
      get_admin_dashboard_snapshot_v1: { Args: Record<PropertyKey, never>; Returns: Json };
      admin_control_and_audit_v1: {
        Args: {
          p_action: string;
          p_actor_id: string;
          p_actor_email: string;
          p_source_url?: string | null;
          p_target_id?: string | null;
        };
        Returns: Json;
      };
      begin_youtube_discovery_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number };
        Returns: { acquired: boolean; retry_at: string | null }[];
      };
      begin_bluesky_jetstream_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number };
        Returns: { acquired: boolean; retry_at: string | null; start_cursor: number | null }[];
      };
      begin_nostr_relay_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number; relay_key: string };
        Returns: {
          acquired: boolean;
          retry_at: string | null;
          since: string;
          until: string;
          checkpoint: string | null;
          recent_candidate_ids: string[];
        }[];
      };
      bluesky_cursor_v1: { Args: { value: string }; Returns: number };
      bluesky_timestamp_v1: {
        Args: { value: string; upper_bound: string };
        Returns: string;
      };
      begin_public_study_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number };
        Returns: { acquired: boolean; retry_at: string | null }[];
      };
      begin_public_study_job_v2: {
        Args: { job_id: string; worker_id: string; lease_generation: number; study_key: string };
        Returns: { acquired: boolean; retry_at: string | null }[];
      };
      begin_tcgdex_sets_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number };
        Returns: { acquired: boolean; retry_at: string | null; etag: string | null; content_sha256: string | null; item_count: number; revision: number }[];
      };
      claim_jobs: { Args: { worker_id: string; job_types?: string[] | null; batch_size?: number; lease_seconds?: number }; Returns: Database['ingest']['Tables']['jobs']['Row'][] };
      claim_jobs_v2: { Args: { worker_id: string; job_types?: string[] | null; batch_size?: number; lease_seconds?: number }; Returns: Database['ingest']['Tables']['jobs']['Row'][] };
      claim_nostr_relay_jobs_v1: {
        Args: { p_worker_id: string; p_lease_seconds: number };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      complete_job_v2: {
        Args: { p_job_id: string; p_worker_id: string; p_lease_generation: number };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      finalize_nostr_relay_job: {
        Args: {
          job_id: string;
          worker_id: string;
          lease_generation: number;
          result: Json;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      nostr_timestamp_v1: {
        Args: { value: string; lower_bound: string; upper_bound: string };
        Returns: string;
      };
      prune_nostr_relay_v1: {
        Args: { cutoff: string; max_rows?: number };
        Returns: { candidates_deleted: number; observations_deleted: number }[];
      };
      enqueue_job_v1: {
        Args: {
          p_job_type: string;
          p_payload?: Json;
          p_priority?: number;
          p_dedupe_key?: string | null;
          p_available_at?: string | null;
          p_max_attempts?: number;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      enqueue_public_study_coverage_job_v1: {
        Args: {
          p_study_key: string;
          p_priority?: number;
          p_dedupe_key?: string | null;
          p_available_at?: string | null;
          p_max_attempts?: number;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      enqueue_scheduled_job_v1: {
        Args: {
          schedule_name: string;
          scheduled_for: string;
          job_type: string;
          payload?: Json;
          priority?: number;
          max_attempts?: number;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      enqueue_scheduled_public_study_coverage_job_v1: {
        Args: {
          p_schedule_name: string;
          p_scheduled_for: string;
          p_study_key: string;
          p_priority?: number;
          p_max_attempts?: number;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      finalize_cleanup_job: { Args: { job_id: string; worker_id: string; lease_generation: number }; Returns: Database['ingest']['Tables']['jobs']['Row'][] };
      verify_nostr_release_v1: { Args: Record<PropertyKey, never>; Returns: Json };
      verify_nostr_release_v2: { Args: Record<PropertyKey, never>; Returns: Json };
      enqueue_due_nostr_relay_jobs_v1: {
        Args: { p_worker_id: string };
        Returns: number;
      };
      nostr_worker_runtime_ready_v1: {
        Args: Record<PropertyKey, never>;
        Returns: boolean;
      };
      get_nostr_worker_policy_snapshot_v1: {
        Args: Record<PropertyKey, never>;
        Returns: {
          source_key: string;
          display_name: string;
          source_kind: string;
          domain: string;
          base_url: string | null;
          enabled: boolean;
          collector_type: string;
          access_mode: string;
          robots_policy: string;
          routes: string[];
          include_subdomains: boolean;
          min_delay_seconds: number;
          max_pages_per_run: number;
          max_items_per_run: number;
          max_concurrency: number;
          browser_profile: string | null;
          statistics_eligible_default: boolean;
          retention_days: number;
          config: Json;
          version: string;
          expected_interval_seconds: number;
          is_demo: boolean;
        }[];
      };
      finalize_tcgdex_sets_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number; result: Json };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      finalize_youtube_discovery_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number; result: Json };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      finalize_bluesky_jetstream_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number; result: Json };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      finalize_public_study_job: {
        Args: { job_id: string; worker_id: string; lease_generation: number; result: Json };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      finalize_public_study_coverage_job_v1: {
        Args: {
          job_id: string;
          worker_id: string;
          lease_generation: number;
          study_key: string;
          result: Json;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      fail_job_v2: {
        Args: {
          job_id: string;
          worker_id: string;
          lease_generation: number;
          error_code: string;
          error_message: string;
          retryable: boolean;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      fail_nostr_relay_job_v1: {
        Args: {
          p_job_id: string;
          p_worker_id: string;
          p_lease_generation: number;
          p_error_code: string;
          p_error_message: string;
          p_retryable: boolean;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      heartbeat_job_v2: {
        Args: { job_id: string; worker_id: string; lease_generation: number; lease_seconds: number };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      heartbeat_nostr_relay_job_v1: {
        Args: {
          p_job_id: string;
          p_worker_id: string;
          p_lease_generation: number;
          p_lease_seconds: number;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      pause_job_for_budget_v2: {
        Args: { p_job_id: string; p_worker_id: string; p_lease_generation: number; p_retry_at: string };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      pause_nostr_relay_job_v1: {
        Args: {
          p_job_id: string;
          p_worker_id: string;
          p_lease_generation: number;
          p_retry_at: string;
        };
        Returns: Database['ingest']['Tables']['jobs']['Row'][];
      };
      prune_expired_ephemera: { Args: { cutoff?: string; max_rows?: number }; Returns: Json };
      prune_expired_ephemera_v2: { Args: { cutoff?: string; max_rows?: number }; Returns: Json };
      prune_bluesky_jetstream_v1: {
        Args: { cutoff: string; max_rows?: number };
        Returns: { candidates_deleted: number; observations_deleted: number }[];
      };
      upsert_nostr_worker_heartbeat_v1: {
        Args: { p_worker_id: string; p_version: string; p_metadata: Json };
        Returns: { last_seen_at: string }[];
      };
      reviewed_public_study_contracts: {
        Args: Record<PropertyKey, never>;
        Returns: {
          ordinal: number;
          study_key: string;
          policy_key: string;
          public_id: string;
          public_name: string;
          public_note: string;
          display_name: string;
          domain: string;
          canonical_url: string;
          policy_version: string;
          config: Json;
          evidence_excerpt: string;
          title_fragments: string[];
        }[];
      };
      upsert_worker_heartbeat_v1: {
        Args: { p_worker_id: string; p_worker_type: string; p_version: string; p_metadata: Json };
        Returns: { last_seen_at: string }[];
      };
    };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
  analytics: {
    Tables: {
      batch_metrics_daily: {
        Row: {
          id: string;
          date: string;
          batch_code: string;
          normalized_batch_code: string;
          set_id: string;
          product_id: string | null;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          region_count: number;
          retailer_count: number;
          first_seen: string;
          last_seen: string;
          posterior_mean: number;
          credible_interval_low: number;
          credible_interval_high: number;
          credible_level: number;
          baseline: number;
          baseline_scope: string;
          probability_above_baseline: number;
          probability_above_practical_uplift: number;
          signal_status: string;
          computed_at: string;
          methodology_version: string;
          is_demo: boolean;
        };
        Insert: {
          id?: string;
          date: string;
          batch_code: string;
          normalized_batch_code: string;
          set_id: string;
          product_id?: string | null;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          region_count?: number;
          retailer_count?: number;
          first_seen: string;
          last_seen: string;
          posterior_mean: number;
          credible_interval_low: number;
          credible_interval_high: number;
          credible_level?: number;
          baseline: number;
          baseline_scope: string;
          probability_above_baseline: number;
          probability_above_practical_uplift: number;
          signal_status: string;
          computed_at?: string;
          methodology_version: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          date?: string;
          batch_code?: string;
          normalized_batch_code?: string;
          set_id?: string;
          product_id?: string | null;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          region_count?: number;
          retailer_count?: number;
          first_seen?: string;
          last_seen?: string;
          posterior_mean?: number;
          credible_interval_low?: number;
          credible_interval_high?: number;
          credible_level?: number;
          baseline?: number;
          baseline_scope?: string;
          probability_above_baseline?: number;
          probability_above_practical_uplift?: number;
          signal_status?: string;
          computed_at?: string;
          methodology_version?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'batch_metrics_daily_product_id_fkey';
            columns: ['product_id'];
            isOneToOne: false;
            referencedRelation: 'products';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'batch_metrics_daily_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
      dashboard_daily: {
        Row: {
          date: string;
          country_code: string;
          language: string;
          observed_packs: number;
          complete_openings: number;
          accepted_sources: number;
          activity_only_sources: number;
          rejected_sources: number;
          tracked_sets: number;
          tracked_regions: number;
          tracked_retailers: number;
          batch_sightings: number;
          data_quality_score: number;
          accepted_count: number;
          activity_only_count: number;
          rejected_count: number;
          hit_count: number;
          observed_hit_rate: number | null;
          posterior_mean: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          baseline: number | null;
          delta_from_baseline: number | null;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          build_sha: string;
          computed_at: string;
          methodology_version: string;
          is_demo: boolean;
        };
        Insert: {
          date: string;
          country_code: string;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          accepted_sources?: number;
          activity_only_sources?: number;
          rejected_sources?: number;
          tracked_sets?: number;
          tracked_regions?: number;
          tracked_retailers?: number;
          batch_sightings?: number;
          data_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          hit_count?: number;
          observed_hit_rate?: number | null;
          posterior_mean?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          baseline?: number | null;
          delta_from_baseline?: number | null;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          build_sha: string;
          computed_at?: string;
          methodology_version: string;
          is_demo?: boolean;
        };
        Update: {
          date?: string;
          country_code?: string;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          accepted_sources?: number;
          activity_only_sources?: number;
          rejected_sources?: number;
          tracked_sets?: number;
          tracked_regions?: number;
          tracked_retailers?: number;
          batch_sightings?: number;
          data_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          hit_count?: number;
          observed_hit_rate?: number | null;
          posterior_mean?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          baseline?: number | null;
          delta_from_baseline?: number | null;
          baseline_scope?: string;
          window_start?: string;
          window_end?: string;
          catalog_version?: string;
          build_sha?: string;
          computed_at?: string;
          methodology_version?: string;
          is_demo?: boolean;
        };
        Relationships: [
        ];
      };
      region_metrics_daily: {
        Row: {
          id: string;
          date: string;
          region_id: string;
          set_id: string | null;
          product_id: string | null;
          product_type: string | null;
          language: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          rarity_counts: Json;
          observed_rates: Json;
          baseline_rates: Json;
          credible_intervals: Json;
          sample_quality_score: number;
          accepted_count: number;
          activity_only_count: number;
          rejected_count: number;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          computed_at: string;
          methodology_version: string;
          is_demo: boolean;
        };
        Insert: {
          id?: string;
          date: string;
          region_id: string;
          set_id?: string | null;
          product_id?: string | null;
          product_type?: string | null;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          rarity_counts?: Json;
          observed_rates?: Json;
          baseline_rates?: Json;
          credible_intervals?: Json;
          sample_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          computed_at?: string;
          methodology_version: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          date?: string;
          region_id?: string;
          set_id?: string | null;
          product_id?: string | null;
          product_type?: string | null;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          rarity_counts?: Json;
          observed_rates?: Json;
          baseline_rates?: Json;
          credible_intervals?: Json;
          sample_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          baseline_scope?: string;
          window_start?: string;
          window_end?: string;
          catalog_version?: string;
          computed_at?: string;
          methodology_version?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'region_metrics_daily_product_id_fkey';
            columns: ['product_id'];
            isOneToOne: false;
            referencedRelation: 'products';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'region_metrics_daily_region_id_fkey';
            columns: ['region_id'];
            isOneToOne: false;
            referencedRelation: 'regions';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'region_metrics_daily_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
      retailer_metrics_daily: {
        Row: {
          id: string;
          date: string;
          retailer_id: string;
          region_id: string | null;
          set_id: string | null;
          product_id: string | null;
          product_type: string | null;
          language: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          rarity_counts: Json;
          observed_rates: Json;
          baseline_rates: Json;
          credible_intervals: Json;
          sample_quality_score: number;
          accepted_count: number;
          activity_only_count: number;
          rejected_count: number;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          computed_at: string;
          methodology_version: string;
          is_demo: boolean;
        };
        Insert: {
          id?: string;
          date: string;
          retailer_id: string;
          region_id?: string | null;
          set_id?: string | null;
          product_id?: string | null;
          product_type?: string | null;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          rarity_counts?: Json;
          observed_rates?: Json;
          baseline_rates?: Json;
          credible_intervals?: Json;
          sample_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          computed_at?: string;
          methodology_version: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          date?: string;
          retailer_id?: string;
          region_id?: string | null;
          set_id?: string | null;
          product_id?: string | null;
          product_type?: string | null;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          rarity_counts?: Json;
          observed_rates?: Json;
          baseline_rates?: Json;
          credible_intervals?: Json;
          sample_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          baseline_scope?: string;
          window_start?: string;
          window_end?: string;
          catalog_version?: string;
          computed_at?: string;
          methodology_version?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'retailer_metrics_daily_product_id_fkey';
            columns: ['product_id'];
            isOneToOne: false;
            referencedRelation: 'products';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'retailer_metrics_daily_region_id_fkey';
            columns: ['region_id'];
            isOneToOne: false;
            referencedRelation: 'regions';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'retailer_metrics_daily_retailer_id_fkey';
            columns: ['retailer_id'];
            isOneToOne: false;
            referencedRelation: 'retailers';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'retailer_metrics_daily_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
      set_metrics_daily: {
        Row: {
          id: string;
          date: string;
          set_id: string;
          product_type: string | null;
          language: string;
          observed_packs: number;
          complete_openings: number;
          independent_source_count: number;
          rarity_counts: Json;
          observed_rates: Json;
          baseline_rates: Json;
          credible_intervals: Json;
          sample_quality_score: number;
          accepted_count: number;
          activity_only_count: number;
          rejected_count: number;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          computed_at: string;
          methodology_version: string;
          is_demo: boolean;
        };
        Insert: {
          id?: string;
          date: string;
          set_id: string;
          product_type?: string | null;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          rarity_counts?: Json;
          observed_rates?: Json;
          baseline_rates?: Json;
          credible_intervals?: Json;
          sample_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          baseline_scope: string;
          window_start: string;
          window_end: string;
          catalog_version: string;
          computed_at?: string;
          methodology_version: string;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          date?: string;
          set_id?: string;
          product_type?: string | null;
          language?: string;
          observed_packs?: number;
          complete_openings?: number;
          independent_source_count?: number;
          rarity_counts?: Json;
          observed_rates?: Json;
          baseline_rates?: Json;
          credible_intervals?: Json;
          sample_quality_score?: number;
          accepted_count?: number;
          activity_only_count?: number;
          rejected_count?: number;
          baseline_scope?: string;
          window_start?: string;
          window_end?: string;
          catalog_version?: string;
          computed_at?: string;
          methodology_version?: string;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'set_metrics_daily_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
      signals: {
        Row: {
          id: string;
          signal_type: string;
          entity_type: string;
          entity_key: string;
          set_id: string | null;
          metric: string;
          status: string;
          sample_size: number;
          independent_source_count: number;
          baseline: number | null;
          observed: number | null;
          posterior_mean: number | null;
          credible_interval_low: number | null;
          credible_interval_high: number | null;
          credible_level: number;
          probability_above_baseline: number | null;
          probability_above_practical_uplift: number | null;
          explanation: Json;
          baseline_scope: string;
          evidence_tier: string;
          methodology_version: string;
          first_detected_at: string;
          last_updated_at: string;
          expires_at: string;
          is_public: boolean;
          is_demo: boolean;
        };
        Insert: {
          id?: string;
          signal_type: string;
          entity_type: string;
          entity_key: string;
          set_id?: string | null;
          metric: string;
          status: string;
          sample_size: number;
          independent_source_count: number;
          baseline?: number | null;
          observed?: number | null;
          posterior_mean?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          probability_above_baseline?: number | null;
          probability_above_practical_uplift?: number | null;
          explanation: Json;
          baseline_scope: string;
          evidence_tier: string;
          methodology_version: string;
          first_detected_at: string;
          last_updated_at: string;
          expires_at: string;
          is_public?: boolean;
          is_demo?: boolean;
        };
        Update: {
          id?: string;
          signal_type?: string;
          entity_type?: string;
          entity_key?: string;
          set_id?: string | null;
          metric?: string;
          status?: string;
          sample_size?: number;
          independent_source_count?: number;
          baseline?: number | null;
          observed?: number | null;
          posterior_mean?: number | null;
          credible_interval_low?: number | null;
          credible_interval_high?: number | null;
          credible_level?: number;
          probability_above_baseline?: number | null;
          probability_above_practical_uplift?: number | null;
          explanation?: Json;
          baseline_scope?: string;
          evidence_tier?: string;
          methodology_version?: string;
          first_detected_at?: string;
          last_updated_at?: string;
          expires_at?: string;
          is_public?: boolean;
          is_demo?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: 'signals_set_id_fkey';
            columns: ['set_id'];
            isOneToOne: false;
            referencedRelation: 'sets';
            referencedColumns: ['id'];
          },
        ];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
    };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
};

export type PublicTables = Database['public']['Tables'];
export type PublicTableName = keyof PublicTables;
export type PublicRow<T extends PublicTableName> = PublicTables[T]['Row'];
export type SchemaName = keyof Database;
