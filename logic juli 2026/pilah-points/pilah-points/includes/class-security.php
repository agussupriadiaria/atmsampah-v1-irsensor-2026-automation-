<?php
if ( ! defined( 'ABSPATH' ) ) exit;

class Pilah_Security {

    public static function check_rate_limit( $user_id, $action, $limit ) {
        global $wpdb;
        $user_id = intval( $user_id );
        $action  = sanitize_key( $action );
        $now     = current_time( 'mysql' );
        $window  = date( 'Y-m-d H:i:s', strtotime( '-1 hour' ) );

        $record = $wpdb->get_row( $wpdb->prepare(
            "SELECT * FROM pilah_rate_limit WHERE user_id = %d AND action = %s",
            $user_id, $action ) );

        if ( ! $record ) {
            $wpdb->insert( 'pilah_rate_limit',
                [ 'user_id' => $user_id, 'action' => $action, 'count' => 1, 'window_start' => $now ],
                [ '%d', '%s', '%d', '%s' ] );
            return true;
        }

        if ( $record->window_start < $window ) {
            $wpdb->query( $wpdb->prepare(
                "UPDATE pilah_rate_limit SET count = 1, window_start = %s WHERE user_id = %d AND action = %s",
                $now, $user_id, $action ) );
            return true;
        }

        if ( intval( $record->count ) >= $limit ) {
            self::write_audit_log( $user_id, 'rate_limit_exceeded', 'transaction', 0,
                null, [ 'action' => $action, 'count' => $record->count, 'limit' => $limit ] );
            return false;
        }

        $wpdb->query( $wpdb->prepare(
            "UPDATE pilah_rate_limit SET count = count + 1 WHERE user_id = %d AND action = %s",
            $user_id, $action ) );
        return true;
    }

    public static function write_audit_log( $user_id, $action, $entity_type, $entity_id, $old = null, $new = null ) {
        global $wpdb;
        $wpdb->insert( 'pilah_audit_log', [
            'user_id'     => intval( $user_id ),
            'action'      => sanitize_text_field( $action ),
            'entity_type' => $entity_type,
            'entity_id'   => intval( $entity_id ),
            'old_value'   => $old ? wp_json_encode( $old ) : null,
            'new_value'   => $new ? wp_json_encode( $new ) : null,
            'ip_address'  => self::get_client_ip(),
            'user_agent'  => isset( $_SERVER['HTTP_USER_AGENT'] )
                             ? substr( $_SERVER['HTTP_USER_AGENT'], 0, 500 ) : null,
        ], [ '%d', '%s', '%s', '%d', '%s', '%s', '%s', '%s' ] );
    }

    public static function sanitize_point_amount( $value ) {
        $amount = floatval( $value );
        if ( $amount <= 0 || $amount > 9999 ) return false;
        return round( $amount, 2 );
    }

    public static function sanitize_tid( $value ) {
        $tid = preg_replace( '/[^a-zA-Z0-9-_]/', '', $value );
        if ( strlen( $tid ) < 1 || strlen( $tid ) > 64 ) return false;
        return $tid;
    }

    public static function get_client_ip() {
        $keys = [ 'HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR' ];
        foreach ( $keys as $k ) {
            if ( ! empty( $_SERVER[ $k ] ) ) {
                $ip = trim( explode( ',', $_SERVER[ $k ] )[0] );
                if ( filter_var( $ip, FILTER_VALIDATE_IP ) ) return $ip;
            }
        }
        return '0.0.0.0';
    }
}
