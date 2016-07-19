describe('adming configure node', function() {
  it('should configure node en internalization', function() {
    browser.setLocation('admin/content');
    element(by.model('GLTranslate.indirect.appLanguage')).element(by.xpath(".//*[text()='English']")).click();
    expect(element(by.model('admin.node.header_title_homepage')).clear().sendKeys('TEXT1_EN'));
    expect(element(by.model('admin.node.presentation')).clear().sendKeys('TEXT2_EN'));
    element(by.css('[data-ng-click="updateNode(admin.node)"]')).click();
  });

  it('should configure node it internalization', function() {
    browser.setLocation('admin/content');
    element(by.model('GLTranslate.indirect.appLanguage')).element(by.xpath(".//*[text()='Italiano']")).click();
    expect(element(by.model('admin.node.header_title_homepage')).clear().sendKeys('TEXT1_IT'));
    expect(element(by.model('admin.node.presentation')).clear().sendKeys('TEXT2_IT'));
    element(by.css('[data-ng-click="updateNode(admin.node)"]')).click();
  });

  it('should configure node advanced settings', function() {
    browser.setLocation('admin/advanced_settings');

    // simplify the configuration in order to simplfy initial tests
    element(by.model('admin.node.disable_security_awareness_badge')).click();

    // enable all receivers to postpone and delete tips
    element(by.model('admin.node.can_postpone_expiration')).click();
    element(by.model('admin.node.can_delete_submission')).click();

    element(by.css('[data-ng-click="updateNode(admin.node)"]')).click();
  });
});
