/**
 * Generated from the backend's OpenAPI document. Do not edit by hand.
 *
 * Run `npm run gen:api` after changing a response shape in f1telemetry/schemas.py.
 */
export interface paths {
    "/api/compare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Compare
         * @description Two laps on one 5 m distance grid, with the delta trace and 25 minisector gains.
         */
        get: operations["compare_api_compare_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sessions
         * @description Saved sessions, newest first.
         */
        get: operations["list_sessions_api_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["get_session_api_sessions__session_id__get"];
        put?: never;
        post?: never;
        /** Delete Session */
        delete: operations["delete_session_api_sessions__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/{session_id}/laps/{number}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Lap
         * @description A lap's samples as columns, served as saved: laps run to hundreds of KB, so they aren't re-encoded.
         */
        get: operations["get_lap_api_sessions__session_id__laps__number__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/setup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Setup */
        get: operations["setup_api_setup_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * CompareColumns
         * @description The traces worth overlaying, resampled onto the shared distance grid.
         */
        CompareColumns: {
            /** Brake */
            brake: number[];
            /** Speed */
            speed: number[];
            /** Steer */
            steer: number[];
            /** Throttle */
            throttle: number[];
        };
        /** CompareLap */
        CompareLap: {
            columns: components["schemas"]["CompareColumns"];
            /** Invalid */
            invalid: boolean;
            /** Lap Time Ms */
            lap_time_ms: number;
            /** Number */
            number: number;
            /** Partial */
            partial: boolean;
            session: components["schemas"]["CompareLapSession"];
        };
        /**
         * CompareLapSession
         * @description Which session a compared lap came from. The track is reported once, on the result, for both.
         */
        CompareLapSession: {
            /** Id */
            id: string | null;
            session_type: components["schemas"]["SessionType"] | null;
            /** Started At */
            started_at: string | null;
        };
        /** CompareResult */
        CompareResult: {
            /**
             * Delta
             * @description seconds lap B has taken more than lap A; positive means B is slower
             */
            delta: number[];
            /** Distance */
            distance: number[];
            /**
             * Laps
             * @description exactly two, in the order asked for
             */
            laps: components["schemas"]["CompareLap"][];
            /** Minisectors */
            minisectors: components["schemas"]["Minisector"][];
            /**
             * Step
             * @description metres between grid points
             */
            step: number;
            track: components["schemas"]["Track"];
        };
        /** ErrorDetail */
        ErrorDetail: {
            /** Detail */
            detail: string;
        };
        /** Formula */
        Formula: {
            /** Id */
            id: number;
            /**
             * Name
             * @description ERS and active aero are gated on the series, not the packet format
             */
            name: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * LapColumns
         * @description One array per channel, all the same length. Column-major so a chart can hand an array straight to uPlot.
         */
        LapColumns: {
            /**
             * Brake
             * @description 0-1
             */
            brake: number[];
            /**
             * Drs
             * @description 0 or 1
             */
            drs: number[];
            /** Engine Rpm */
            engine_rpm: number[];
            /**
             * Gear
             * @description -1 reverse, 0 neutral, 1-8
             */
            gear: number[];
            /**
             * Lap Distance
             * @description metres; negative before the start line
             */
            lap_distance: number[];
            /** Lap Time Ms */
            lap_time_ms: number[];
            /**
             * Session Time
             * @description seconds
             */
            session_time: number[];
            /**
             * Speed
             * @description km/h
             */
            speed: number[];
            /**
             * Steer
             * @description -1 full left to 1 full right
             */
            steer: number[];
            /**
             * Throttle
             * @description 0-1
             */
            throttle: number[];
        };
        /** LapDocument */
        LapDocument: {
            columns: components["schemas"]["LapColumns"];
            /** Invalid */
            invalid: boolean;
            /** Lap Time Ms */
            lap_time_ms: number;
            /** Number */
            number: number;
            /**
             * Partial
             * @description the lap was not driven end to end, e.g. an out lap or a flashback
             */
            partial: boolean;
            /** Samples */
            samples: number;
            /** Version */
            version: number;
        };
        /** LapSummary */
        LapSummary: {
            /** Invalid */
            invalid: boolean;
            /** Lap Time Ms */
            lap_time_ms: number;
            /** Number */
            number: number;
            /**
             * Partial
             * @description the lap was not driven end to end, e.g. an out lap or a flashback
             */
            partial: boolean;
            /** Samples */
            samples: number;
        };
        /** @enum {string} */
        ListenMode: "local" | "network";
        /**
         * LiveDamage
         * @description The latest CarDamage packet.
         */
        LiveDamage: {
            /** Brake Damage Fl */
            brake_damage_fl: number;
            /** Brake Damage Fr */
            brake_damage_fr: number;
            /** Brake Damage Rl */
            brake_damage_rl: number;
            /** Brake Damage Rr */
            brake_damage_rr: number;
            /** Diffuser Damage */
            diffuser_damage: number;
            /** Drs Fault */
            drs_fault: boolean;
            /** Engine Damage */
            engine_damage: number;
            /** Ers Fault */
            ers_fault: boolean;
            /** Floor Damage */
            floor_damage: number;
            /** Front Left Wing Damage */
            front_left_wing_damage: number;
            /** Front Right Wing Damage */
            front_right_wing_damage: number;
            /** Gearbox Damage */
            gearbox_damage: number;
            /** Rear Wing Damage */
            rear_wing_damage: number;
            /** Sidepod Damage */
            sidepod_damage: number;
            /** Tyre Blisters Fl */
            tyre_blisters_fl: number;
            /** Tyre Blisters Fr */
            tyre_blisters_fr: number;
            /** Tyre Blisters Rl */
            tyre_blisters_rl: number;
            /** Tyre Blisters Rr */
            tyre_blisters_rr: number;
            /** Tyre Damage Fl */
            tyre_damage_fl: number;
            /** Tyre Damage Fr */
            tyre_damage_fr: number;
            /** Tyre Damage Rl */
            tyre_damage_rl: number;
            /** Tyre Damage Rr */
            tyre_damage_rr: number;
            /** Tyre Wear Fl */
            tyre_wear_fl: number;
            /** Tyre Wear Fr */
            tyre_wear_fr: number;
            /** Tyre Wear Rl */
            tyre_wear_rl: number;
            /** Tyre Wear Rr */
            tyre_wear_rr: number;
        };
        /** LiveDelta */
        LiveDelta: {
            /** Best Lap */
            best_lap: number;
            /**
             * Seconds
             * @description gap to the session's best lap at this distance; positive means slower
             */
            seconds: number;
        };
        /**
         * LiveHello
         * @description Sent once on connect, with the open session or null.
         */
        LiveHello: {
            session: components["schemas"]["SessionDocument"] | null;
            /**
             * Type
             * @constant
             */
            type: "hello";
        };
        /**
         * LiveLap
         * @description The latest LapData packet for the player's car.
         */
        LiveLap: {
            /** Car Position */
            car_position: number;
            /** Corner Cutting Warnings */
            corner_cutting_warnings: number;
            /** Current Lap Invalid */
            current_lap_invalid: boolean;
            /** Current Lap Num */
            current_lap_num: number;
            /** Current Lap Time Ms */
            current_lap_time_ms: number;
            /** Delta To Car In Front Ms */
            delta_to_car_in_front_ms: number;
            /** Delta To Race Leader Ms */
            delta_to_race_leader_ms: number;
            /** Driver Status */
            driver_status: number;
            /** Grid Position */
            grid_position: number;
            /** Lap Distance */
            lap_distance: number;
            /** Last Lap Time Ms */
            last_lap_time_ms: number;
            /** Num Pit Stops */
            num_pit_stops: number;
            /** Penalties */
            penalties: number;
            /** Pit Status */
            pit_status: number;
            /** Result Status */
            result_status: number;
            /** Safety Car Delta */
            safety_car_delta: number;
            /** Sector */
            sector: number;
            /** Sector1 Time Ms */
            sector1_time_ms: number;
            /** Sector2 Time Ms */
            sector2_time_ms: number;
            /** Total Distance */
            total_distance: number;
            /** Total Warnings */
            total_warnings: number;
            /** Unserved Drive Through Pens */
            unserved_drive_through_pens: number;
            /** Unserved Stop Go Pens */
            unserved_stop_go_pens: number;
        };
        /** LiveLapCompleted */
        LiveLapCompleted: {
            lap: components["schemas"]["LapSummary"];
            session: components["schemas"]["SessionDocument"] | null;
            /**
             * Type
             * @constant
             */
            type: "lap_completed";
        };
        /**
         * LiveLapReopened
         * @description A flashback took a finished lap back; the client should drop it and wait for it again.
         */
        LiveLapReopened: {
            /** Lap Number */
            lap_number: number;
            session: components["schemas"]["SessionDocument"] | null;
            /**
             * Type
             * @constant
             */
            type: "lap_reopened";
        };
        /**
         * LiveSession
         * @description The latest Session packet.
         */
        LiveSession: {
            /** Active Aero Track Status */
            active_aero_track_status: number | null;
            /** Active Aero Zones Full */
            active_aero_zones_full: components["schemas"]["Zone"][];
            /** Active Aero Zones Partial */
            active_aero_zones_partial: components["schemas"]["Zone"][];
            /** Air Temperature */
            air_temperature: number;
            /** Formula */
            formula: number;
            /** Game Paused */
            game_paused: boolean;
            /** Is Spectating */
            is_spectating: boolean;
            /** Pit Speed Limit */
            pit_speed_limit: number;
            /** Sector2 Lap Distance Start */
            sector2_lap_distance_start: number;
            /** Sector3 Lap Distance Start */
            sector3_lap_distance_start: number;
            /** Session Duration */
            session_duration: number;
            /** Session Time Left */
            session_time_left: number;
            /** Session Type */
            session_type: number;
            /** Total Laps */
            total_laps: number;
            /** Track Id */
            track_id: number;
            /** Track Length */
            track_length: number;
            /** Track Temperature */
            track_temperature: number;
            /** Weather */
            weather: number;
        };
        /** LiveSessionEnded */
        LiveSessionEnded: {
            /** Reason */
            reason: string;
            session: components["schemas"]["SessionDocument"] | null;
            /**
             * Type
             * @constant
             */
            type: "session_ended";
        };
        /** LiveSessionStarted */
        LiveSessionStarted: {
            session: components["schemas"]["SessionDocument"] | null;
            /**
             * Type
             * @constant
             */
            type: "session_started";
        };
        /**
         * LiveSnapshot
         * @description Sent at 30 Hz while the picture changes. Every packet slot is null until one of that kind has arrived.
         */
        LiveSnapshot: {
            /**
             * Connected
             * @description a datagram arrived within the last second
             */
            connected: boolean;
            damage: components["schemas"]["LiveDamage"] | null;
            delta: components["schemas"]["LiveDelta"] | null;
            lap: components["schemas"]["LiveLap"] | null;
            /** Packet Format */
            packet_format: number | null;
            /** Packets Per Second */
            packets_per_second: number;
            /** Player Index */
            player_index: number | null;
            session: components["schemas"]["LiveSession"] | null;
            status: components["schemas"]["LiveStatus"] | null;
            telemetry: components["schemas"]["LiveTelemetry"] | null;
            telemetry2: components["schemas"]["LiveTelemetry2"] | null;
            /**
             * Type
             * @constant
             */
            type: "snapshot";
        };
        /**
         * LiveStatus
         * @description The latest CarStatus packet.
         */
        LiveStatus: {
            /** Actual Tyre Compound */
            actual_tyre_compound: number;
            /** Anti Lock Brakes */
            anti_lock_brakes: boolean;
            /** Drs Activation Distance */
            drs_activation_distance: number;
            /** Drs Allowed */
            drs_allowed: boolean;
            /** Engine Power Ice */
            engine_power_ice: number;
            /** Engine Power Mguk */
            engine_power_mguk: number;
            /** Ers Deploy Mode */
            ers_deploy_mode: number;
            /** Ers Deployed This Lap */
            ers_deployed_this_lap: number;
            /** Ers Harvest Limit Per Lap */
            ers_harvest_limit_per_lap: number | null;
            /** Ers Harvested This Lap Mguh */
            ers_harvested_this_lap_mguh: number;
            /** Ers Harvested This Lap Mguk */
            ers_harvested_this_lap_mguk: number;
            /** Ers Store Energy */
            ers_store_energy: number;
            /** Fia Flag */
            fia_flag: number;
            /** Front Brake Bias */
            front_brake_bias: number;
            /** Fuel Capacity */
            fuel_capacity: number;
            /** Fuel In Tank */
            fuel_in_tank: number;
            /** Fuel Mix */
            fuel_mix: number;
            /** Fuel Remaining Laps */
            fuel_remaining_laps: number;
            /** Idle Rpm */
            idle_rpm: number;
            /** Max Gears */
            max_gears: number;
            /** Max Rpm */
            max_rpm: number;
            /** Pit Limiter */
            pit_limiter: boolean;
            /** Traction Control */
            traction_control: number;
            /** Tyres Age Laps */
            tyres_age_laps: number;
            /** Visual Tyre Compound */
            visual_tyre_compound: number;
        };
        /**
         * LiveTelemetry
         * @description The latest CarTelemetry packet.
         */
        LiveTelemetry: {
            /** Brake */
            brake: number;
            /** Brake Temperature Fl */
            brake_temperature_fl: number;
            /** Brake Temperature Fr */
            brake_temperature_fr: number;
            /** Brake Temperature Rl */
            brake_temperature_rl: number;
            /** Brake Temperature Rr */
            brake_temperature_rr: number;
            /** Clutch */
            clutch: number;
            /** Drs */
            drs: boolean;
            /** Engine Rpm */
            engine_rpm: number;
            /** Engine Temperature */
            engine_temperature: number;
            /** Gear */
            gear: number;
            /** Rev Lights Percent */
            rev_lights_percent: number;
            /** Speed */
            speed: number;
            /** Steer */
            steer: number;
            /** Throttle */
            throttle: number;
            /** Tyre Inner Temperature Fl */
            tyre_inner_temperature_fl: number;
            /** Tyre Inner Temperature Fr */
            tyre_inner_temperature_fr: number;
            /** Tyre Inner Temperature Rl */
            tyre_inner_temperature_rl: number;
            /** Tyre Inner Temperature Rr */
            tyre_inner_temperature_rr: number;
            /** Tyre Pressure Fl */
            tyre_pressure_fl: number;
            /** Tyre Pressure Fr */
            tyre_pressure_fr: number;
            /** Tyre Pressure Rl */
            tyre_pressure_rl: number;
            /** Tyre Pressure Rr */
            tyre_pressure_rr: number;
            /** Tyre Surface Temperature Fl */
            tyre_surface_temperature_fl: number;
            /** Tyre Surface Temperature Fr */
            tyre_surface_temperature_fr: number;
            /** Tyre Surface Temperature Rl */
            tyre_surface_temperature_rl: number;
            /** Tyre Surface Temperature Rr */
            tyre_surface_temperature_rr: number;
        };
        /**
         * LiveTelemetry2
         * @description The latest CarTelemetry2 packet; absent in format 2025. `regulations_2026_applicable` is what active aero gates on, and it is False for F2 even though the Session packet still lists four aero zones.
         */
        LiveTelemetry2: {
            /** Active Aero Activation Distance */
            active_aero_activation_distance: number;
            /** Active Aero Available */
            active_aero_available: boolean;
            /** Active Aero Mode */
            active_aero_mode: number;
            /** Is Driving Wrong Way */
            is_driving_wrong_way: boolean;
            /** Overtake Activation Distance */
            overtake_activation_distance: number;
            /** Overtake Active */
            overtake_active: boolean;
            /** Overtake Available */
            overtake_available: boolean;
            /** Regulations 2026 Applicable */
            regulations_2026_applicable: boolean;
        };
        /** Minisector */
        Minisector: {
            /**
             * Delta
             * @description seconds gained or lost inside this slice alone, not a running total
             */
            delta: number;
            /** End */
            end: number;
            /**
             * Start
             * @description metres
             */
            start: number;
        };
        /**
         * SessionDocument
         * @description A saved `session.json`, which is also what every `/ws/live` event carries.
         */
        SessionDocument: {
            /**
             * Best Lap
             * @description fastest lap that is valid and complete
             */
            best_lap: number | null;
            /** End Reason */
            end_reason: string | null;
            /** Ended At */
            ended_at: string | null;
            formula: components["schemas"]["Formula"];
            /** Id */
            id: string;
            /** Laps */
            laps: components["schemas"]["LapSummary"][];
            /** Packet Format */
            packet_format: number;
            /** Player Index */
            player_index: number;
            session_type: components["schemas"]["SessionType"];
            /** Started At */
            started_at: string;
            /** Total Laps */
            total_laps: number;
            track: components["schemas"]["Track"];
            /** Uid */
            uid: string;
            /** Version */
            version: number;
        };
        /**
         * SessionSummary
         * @description A session over the REST API, which adds how the recording ended.
         */
        SessionSummary: {
            /**
             * Best Lap
             * @description fastest lap that is valid and complete
             */
            best_lap: number | null;
            /** End Reason */
            end_reason: string | null;
            /** Ended At */
            ended_at: string | null;
            formula: components["schemas"]["Formula"];
            /** Id */
            id: string;
            /** Laps */
            laps: components["schemas"]["LapSummary"][];
            /** Packet Format */
            packet_format: number;
            /** Player Index */
            player_index: number;
            session_type: components["schemas"]["SessionType"];
            /** Started At */
            started_at: string;
            /**
             * Status
             * @description `interrupted` when the app stopped writing without the session ending
             * @enum {string}
             */
            status: "recording" | "complete" | "interrupted";
            /** Total Laps */
            total_laps: number;
            track: components["schemas"]["Track"];
            /** Uid */
            uid: string;
            /** Version */
            version: number;
        };
        /** SessionType */
        SessionType: {
            /** Id */
            id: number;
            /** Name */
            name: string;
        };
        /** SetupInfo */
        SetupInfo: {
            /** Connected */
            connected: boolean;
            /** Lan Addresses */
            lan_addresses: string[];
            listen_mode: components["schemas"]["ListenMode"];
            /** Packet Errors */
            packet_errors: number;
            /** Packet Format */
            packet_format: number | null;
            /** Packet Warning */
            packet_warning: string | null;
            /** Udp Host */
            udp_host: string;
            /** Udp Port */
            udp_port: number;
        };
        /** Track */
        Track: {
            /** Id */
            id: number;
            /**
             * Length
             * @description metres
             */
            length: number;
            /** Name */
            name: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        Zone: [
            number,
            number
        ];
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    compare_api_compare_get: {
        parameters: {
            query: {
                lap_a: number;
                lap_b: number;
                session_a: string;
                session_b: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompareResult"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorDetail"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    list_sessions_api_sessions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionSummary"][];
                };
            };
        };
    };
    get_session_api_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionSummary"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_session_api_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorDetail"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lap_api_sessions__session_id__laps__number__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LapDocument"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    setup_api_setup_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SetupInfo"];
                };
            };
        };
    };
}
