const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(
    path.join(__dirname, '../frontend/customer/meta-whatsapp.js'), 'utf8'
);

for (const sdkAlreadyLoaded of [false, true]) {
    test(`Embedded Signup preserves configuration with ${sdkAlreadyLoaded ? 'an existing' : 'a newly loaded'} SDK`, async () => {
        const calls = {init: [], login: [], api: [], scripts: []};
        const config = {
            ready: true,
            app_id: '12345',
            config_id: '67890',
            graph_api_version: 'v26.0',
            feature_type: null,
            session_info_version: null
        };
        const FB = {
            init(options) { calls.init.push(options); },
            login(callback, options) { calls.login.push(options); }
        };
        const window = {addEventListener() {}};
        const context = vm.createContext({
            window, URL,
            api: async endpoint => { calls.api.push(endpoint); return {...config}; },
            alert(message) { assert.fail(message); },
            document: {
                getElementById: () => null,
                createElement: () => ({}),
                head: {appendChild(script) {
                    calls.scripts.push(script.src);
                    window.FB = context.FB = FB;
                    window.fbAsyncInit();
                }}
            }
        });
        if (sdkAlreadyLoaded) window.FB = context.FB = FB;
        vm.runInContext(source, context);

        await window.openCustomerMetaWhatsAppConnect(7);
        assert.equal(calls.init.length, 1);
        assert.equal(calls.init[0].appId, config.app_id);
        assert.equal(calls.init[0].version, config.graph_api_version);
        assert.equal(calls.init[0].fedCM, false,
            'Meta can default to FedCM, whose credential request drops config_id and code response options');
        assert.deepEqual(JSON.parse(JSON.stringify(calls.login)), [{
            config_id: config.config_id,
            response_type: 'code',
            override_default_response_type: true,
            extras: {setup: {}, version: 'v4'}
        }]);
        assert.deepEqual(calls.api, ['/customer/meta/whatsapp/embedded-signup/config?agent_id=7']);
        assert.equal(calls.scripts.length, sdkAlreadyLoaded ? 0 : 1);

        // A subsequent attempt must still disable FedCM and honor the server's
        // explicitly selected onboarding options after the SDK is already present.
        config.feature_type = 'whatsapp_business_app_onboarding';
        config.session_info_version = '3';
        await window.openCustomerMetaWhatsAppConnect(7);
        assert.equal(calls.init[1].fedCM, false);
        assert.deepEqual(JSON.parse(JSON.stringify(calls.login[1])), {
            config_id: config.config_id,
            response_type: 'code',
            override_default_response_type: true,
            extras: {
                setup: {},
                version: 'v4',
                featureType: 'whatsapp_business_app_onboarding',
                sessionInfoVersion: '3'
            }
        });
    });
}
