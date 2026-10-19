<?php
defined('BASEPATH') OR exit('No direct script access allowed');

/*
|--------------------------------------------------------------------------
| Project Atlas — FastAPI Agent Backend Configuration
|--------------------------------------------------------------------------
| Configuration parameters for the Python FastAPI Copilot service.
*/

$config['atlas_api_base_url'] = getenv('ATLAS_API_URL') ?: 'http://localhost:8000';
$config['atlas_api_timeout']  = (int)(getenv('ATLAS_API_TIMEOUT') ?: 30); // 30-second budget
$config['atlas_api_key']      = getenv('ATLAS_API_KEY') ?: 'atlas_secret_token_2025';
$config['atlas_default_client'] = getenv('ATLAS_DEFAULT_CLIENT') ?: 'C-01';
