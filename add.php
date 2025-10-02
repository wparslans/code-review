<?php
/**
 * Plugin Name: WP Tester
 * Description: A simple plugin for testing WordPress hooks and shortcodes.
 * Version: 1.0
 * Author: Your Name
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit; // Exit if accessed directly
}

class WP_Tester {

    public function __construct() {
        // Hook into WordPress
        add_action( 'init', [ $this, 'register_shortcode' ] );
        add_action( 'admin_notices', [ $this, 'admin_notice' ] );
    }

    /**
     * Register a test shortcode.
     * Usage: [tester message="Hello World!"]
     */
    public function register_shortcode() {
        add_shortcode( 'tester', [ $this, 'shortcode_output' ] );
    }

    /**
     * Shortcode output
     */
    public function shortcode_output( $atts ) {
        $atts = shortcode_atts(
            [ 'message' => 'This is a test message!' ],
            $atts,
            'tester'
        );

        return '<div class="tester-box" style="padding:10px; border:1px solid #ccc; margin:10px 0; background:#f9f9f9;">' 
            . esc_html( $atts['message'] ) 
            . '</div>';
    }

    /**
     * Show admin notice
     */
    public function admin_notice() {
        echo '<div class="notice notice-success is-dismissible">
            <p><strong>WP Tester is active!</strong> Use shortcode <code>[tester]</code> to test output.</p>
        </div>';
    }
}

// Initialize
new WP_Tester();
