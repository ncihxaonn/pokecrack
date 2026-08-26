// Hand-generated-style bridge for Supabase clients.
// Regenerate with `supabase gen types typescript --local` once the live CLI is available.
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type ProductType = 'booster_box' | 'etb' | 'booster_bundle' | 'blister' | 'collection' | 'tin' | 'other';
export type PublicSignalStatus = 'Insufficient sample' | 'No significant signal' | 'Watch' | 'Possible anomaly';

export type Database = {
  public: {
    Tables: {
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
    };
    Enums: { [_ in never]: never };
    CompositeTypes: { [_ in never]: never };
  };
  catalog: {
    Tables: {
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
            foreignKeyName: 'source_items_duplicate_cluster_id_fkey';
            columns: ['duplicate_cluster_id'];
            isOneToOne: false;
            referencedRelation: 'source_items';
            referencedColumns: ['id'];
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
      claim_jobs: { Args: { worker_id: string; job_types?: string[] | null; batch_size?: number; lease_seconds?: number }; Returns: Database['ingest']['Tables']['jobs']['Row'][] };
      claim_jobs_v2: { Args: { worker_id: string; job_types?: string[] | null; batch_size?: number; lease_seconds?: number }; Returns: Database['ingest']['Tables']['jobs']['Row'][] };
      finalize_cleanup_job: { Args: { job_id: string; worker_id: string; lease_generation: number }; Returns: Database['ingest']['Tables']['jobs']['Row'][] };
      prune_expired_ephemera: { Args: { cutoff?: string; max_rows?: number }; Returns: Json };
      prune_expired_ephemera_v2: { Args: { cutoff?: string; max_rows?: number }; Returns: Json };
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
